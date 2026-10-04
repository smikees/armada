<?php
declare(strict_types=1);
require __DIR__ . '/relay.php';

$root = $argv[1] ?? throw new RuntimeException('Pass a disposable test directory');
if (!is_dir($root) && !mkdir($root, 0700, true)) throw new RuntimeException('Cannot create test directory');
$checks = 0;
function check(bool $ok, string $why): void {
    global $checks;
    if (!$ok) throw new RuntimeException($why);
    $checks++;
}
function fixture(string $name, array $extra = []): array {
    global $root;
    $dir = $root . '/' . $name;
    if (!is_dir($dir)) mkdir($dir, 0700);
    return array_merge(['api_key' => 're_fake_test_only', 'rate_salt' => str_repeat('s', 32), 'state_dir' => $dir], $extra);
}
function report(array $changes = []): array {
    return array_merge(['id' => bin2hex(random_bytes(16)), 'subject' => '[ARMADA beta] Test',
                        'text' => 'The exact approved report', 'reply_to' => 'person@example.org'], $changes);
}
$server = ['REQUEST_METHOD' => 'POST', 'CONTENT_TYPE' => 'application/json', 'REMOTE_ADDR' => '192.0.2.1'];
$config = fixture('success'); $input = report(); $calls = [];
$deliver = function($payload, $key, $id) use (&$calls): bool { $calls[] = [$payload, $key, $id]; return true; };
$run = fn($input, $config, $transport = null) => armada_report($server, json_encode($input), $config, $transport ?? $deliver);
check($run($input, $config)[0] === 200, 'valid report sends');
check($calls[0][0]['to'] === ['armada@stamih.com'], 'recipient is fixed');
check($calls[0][0]['text'] === $input['text'], 'preview is unchanged');
check($calls[0][0]['reply_to'] === $input['reply_to'], 'reply address preserved');
check($run($input, $config)[0] === 200 && count($calls) === 1, 'duplicate does not send again');
check($run(array_merge($input, ['text' => 'changed']), $config)[0] === 409, 'ID cannot change payload');
check($run(report(['to' => ['attacker@example.org']]), $config)[0] === 400, 'recipient override rejected');
check($run(report(['subject' => "[ARMADA beta] x\r\nBcc: bad"]), $config)[0] === 400, 'header injection rejected');
check($run(report(['reply_to' => "a@b.c\r\nx"]), $config)[0] === 400, 'bad reply address rejected');
check($run(report(['text' => str_repeat('x', 65537)]), $config)[0] === 413, 'request bounded');
check(armada_report($server, '{', $config, $deliver)[0] === 400, 'invalid JSON rejected');
check(armada_report(array_merge($server, ['REQUEST_METHOD' => 'GET']), '', $config, $deliver)[0] === 405, 'POST only');
check(armada_report(array_merge($server, ['CONTENT_TYPE' => 'text/plain']), '{}', $config, $deliver)[0] === 415, 'JSON only');

$config = fixture('ip-limit', ['hourly_ip_limit' => 1]);
check($run(report(), $config)[0] === 200 && $run(report(), $config)[0] === 429, 'IP rate limit');
$config = fixture('daily-limit', ['daily_limit' => 1]);
check($run(report(), $config)[0] === 200 && $run(report(), $config)[0] === 429, 'global daily budget');
$config = fixture('hour-limit', ['hourly_limit' => 1]);
check($run(report(), $config)[0] === 200, 'first hourly send');
check(armada_report(array_merge($server, ['REMOTE_ADDR' => '192.0.2.2']), json_encode(report()), $config, $deliver)[0] === 429, 'global hourly budget across IPs');

$config = fixture('retry'); $input = report(); $ids = [];
$uncertain = function($payload, $key, $id) use (&$ids): bool { $ids[] = $id; return count($ids) > 1; };
check($run($input, $config, $uncertain)[0] === 502, 'uncertain provider delivery is not success');
check($run($input, $config, $uncertain)[0] === 200 && $ids[0] === $ids[1], 'retry uses provider idempotency key');
$config = fixture('corrupt'); file_put_contents($config['state_dir'] . '/reports.json', '{broken');
check($run(report(), $config)[0] === 503, 'corrupt state fails closed');
check(file_get_contents($config['state_dir'] . '/reports.json') === '{broken', 'corrupt evidence preserved');
$config = fixture('locked'); $held = fopen($config['state_dir'] . '/reports.lock', 'c'); flock($held, LOCK_EX);
check($run(report(), $config)[0] === 503, 'concurrent lock excludes second sender');
flock($held, LOCK_UN); fclose($held);
check($run(report(), array_merge($config, ['api_key' => '']))[0] === 503, 'missing key fails closed');
echo "$checks relay assertions passed; no network used\n";
