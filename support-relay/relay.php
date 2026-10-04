<?php
declare(strict_types=1);

/* Private library: deploy outside every public document root. No client-supplied recipient. */
function armada_report(array $server, string $raw, array $config, ?callable $deliver = null): array {
    if (($server['REQUEST_METHOD'] ?? '') !== 'POST') return [405, ['ok' => false]];
    if (strlen($raw) > 65536) return [413, ['ok' => false]];
    if (strtolower(explode(';', $server['CONTENT_TYPE'] ?? '')[0]) !== 'application/json') {
        return [415, ['ok' => false]];
    }
    try { $input = json_decode($raw, true, 16, JSON_THROW_ON_ERROR); }
    catch (JsonException $e) { return [400, ['ok' => false]]; }
    if (!is_array($input) || array_diff(array_keys($input), ['id', 'subject', 'text', 'reply_to']) ||
        !is_string($input['id'] ?? null) || !preg_match('/^[a-f0-9]{32}$/D', $input['id']) ||
        !is_string($input['subject'] ?? null) || strlen($input['subject']) > 400 ||
        !str_starts_with($input['subject'], '[ARMADA beta] ') || preg_match('/[\r\n]/', $input['subject']) ||
        !is_string($input['text'] ?? null) || strlen($input['text']) < 1 || strlen($input['text']) > 60000 ||
        !is_string($input['reply_to'] ?? '') ||
        (($input['reply_to'] ?? '') !== '' && !filter_var($input['reply_to'], FILTER_VALIDATE_EMAIL))) {
        return [400, ['ok' => false]];
    }
    if (!is_string($config['api_key'] ?? null) || !str_starts_with($config['api_key'], 're_') ||
        !is_string($config['state_dir'] ?? null) || !is_dir($config['state_dir']) ||
        !is_string($config['rate_salt'] ?? null) || strlen($config['rate_salt']) < 32) {
        return [503, ['ok' => false]];
    }
    $dir = $config['state_dir'];
    $lock = @fopen($dir . '/reports.lock', 'c');
    if (!$lock) return [503, ['ok' => false]];
    // Fail quickly under contention. The provider request also has a strict deadline.
    if (!flock($lock, LOCK_EX | LOCK_NB)) { fclose($lock); return [503, ['ok' => false]]; }
    try {
        $file = $dir . '/reports.json';
        $state = is_file($file) ? json_decode((string)file_get_contents($file), true, 32, JSON_THROW_ON_ERROR)
                               : ['requests' => [], 'reports' => []];
        if (!is_array($state) || !is_array($state['requests'] ?? null) || !is_array($state['reports'] ?? null)) {
            throw new RuntimeException('Invalid state');
        }
        $now = time();
        foreach ($state['requests'] as $ip => $stamps) {
            if (!is_array($stamps)) throw new RuntimeException('Invalid request history');
            $state['requests'][$ip] = array_values(array_filter($stamps, fn($stamp) => is_int($stamp) && $stamp > $now - 3600));
            if (!$state['requests'][$ip]) unset($state['requests'][$ip]);
        }
        foreach ($state['reports'] as $id => $record) {
            if (!is_array($record) || !is_int($record['at'] ?? null) || !is_string($record['hash'] ?? null) ||
                !in_array($record['status'] ?? '', ['pending', 'sent'], true)) throw new RuntimeException('Invalid report history');
            if ($record['at'] < $now - 86400) unset($state['reports'][$id]);
        }
        // Never trust X-Forwarded-For from callers. Configure trusted proxy handling at the web server.
        $ip = hash_hmac('sha256', $server['REMOTE_ADDR'] ?? 'unknown', $config['rate_salt']);
        $requests = $state['requests'][$ip] ?? [];
        $allRequests = array_sum(array_map('count', $state['requests']));
        if (count($requests) >= ($config['hourly_ip_limit'] ?? 5) || $allRequests >= ($config['hourly_limit'] ?? 40)) {
            return [429, ['ok' => false]];
        }
        $id = $input['id'];
        $payload = ['from' => 'ARMADA reports <reports@armada.stamih.com>', 'to' => ['armada@stamih.com'],
                    'subject' => $input['subject'], 'text' => $input['text']];
        if (($input['reply_to'] ?? '') !== '') $payload['reply_to'] = $input['reply_to'];
        $hash = hash('sha256', json_encode($payload, JSON_THROW_ON_ERROR));
        $prior = $state['reports'][$id] ?? null;
        if ($prior && !hash_equals($prior['hash'], $hash)) return [409, ['ok' => false]];
        if (!$prior && count($state['reports']) >= ($config['daily_limit'] ?? 80)) return [429, ['ok' => false]];
        $state['requests'][$ip][] = $now;
        $state['reports'][$id] = $prior ?? ['at' => $now, 'hash' => $hash, 'status' => 'pending'];
        armada_store_reports($file, $state); // Reserve quota before any external effect.
        if (($prior['status'] ?? '') === 'sent') return [200, ['ok' => true]];
        $deliver ??= 'armada_deliver_report';
        // A retry after a lost response uses Resend's same idempotency key and same payload.
        if (!$deliver($payload, $config['api_key'], 'armada-report/' . $id)) return [502, ['ok' => false]];
        $state['reports'][$id]['status'] = 'sent';
        armada_store_reports($file, $state);
        return [200, ['ok' => true]];
    } catch (Throwable $error) {
        // No request contents, credentials or provider error bodies enter responses or logs.
        return [503, ['ok' => false]];
    } finally {
        flock($lock, LOCK_UN);
        fclose($lock);
    }
}

function armada_store_reports(string $path, array $state): void {
    $temp = $path . '.' . bin2hex(random_bytes(8)) . '.tmp';
    $stream = fopen($temp, 'xb');
    if (!$stream) throw new RuntimeException('Cannot save report state');
    try {
        chmod($temp, 0600);
        $bytes = json_encode($state, JSON_THROW_ON_ERROR);
        if (fwrite($stream, $bytes) !== strlen($bytes) || !fflush($stream)) throw new RuntimeException('Incomplete state');
        if (function_exists('fsync') && !fsync($stream)) throw new RuntimeException('Cannot flush report state');
    } finally { fclose($stream); }
    if (!rename($temp, $path)) { @unlink($temp); throw new RuntimeException('Cannot replace report state'); }
}

function armada_deliver_report(array $payload, string $key, string $id): bool {
    $curl = curl_init('https://api.resend.com/emails');
    if ($curl === false) return false;
    try {
        curl_setopt_array($curl, [CURLOPT_POST => true, CURLOPT_RETURNTRANSFER => true,
            CURLOPT_FOLLOWLOCATION => false, CURLOPT_CONNECTTIMEOUT => 4, CURLOPT_TIMEOUT => 12,
            CURLOPT_SSL_VERIFYPEER => true, CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $key, 'Content-Type: application/json', 'Idempotency-Key: ' . $id],
            CURLOPT_POSTFIELDS => json_encode($payload, JSON_THROW_ON_ERROR)]);
        $body = curl_exec($curl);
        $status = curl_getinfo($curl, CURLINFO_HTTP_CODE);
        $result = is_string($body) ? json_decode($body, true) : null;
        return $status >= 200 && $status < 300 && is_array($result) && is_string($result['id'] ?? null);
    } finally { curl_close($curl); }
}
