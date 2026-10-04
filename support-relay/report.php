<?php
declare(strict_types=1);

/* Public entry point: deploy as /api/report.php. Configure an absolute PRIVATE path below,
   or set ARMADA_REPORT_PRIVATE in the PHP environment. Never put a mail key in this file. */
$private = getenv('ARMADA_REPORT_PRIVATE') ?: '/REPLACE_WITH_PRIVATE_PATH/armada-reports';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
ini_set('display_errors', '0');
try {
    if (!is_file($private . '/config.php') || !is_file($private . '/relay.php')) throw new RuntimeException();
    require $private . '/relay.php';
    $config = require $private . '/config.php';
    $input = fopen('php://input', 'rb');
    $raw = $input ? stream_get_contents($input, 65537) : '';
    if ($input) fclose($input);
    [$status, $result] = armada_report($_SERVER, $raw, $config);
} catch (Throwable $error) { $status = 503; $result = ['ok' => false]; }
http_response_code($status);
if ($status === 429 || $status === 503) header('Retry-After: 60');
echo json_encode($result);
