<?php
/* Fill only in the private hosting directory. Never commit the completed file. */
return [
    'api_key' => 'REPLACE_WITH_NEW_SENDING_ONLY_RESEND_KEY',
    'rate_salt' => 'REPLACE_WITH_AT_LEAST_32_RANDOM_CHARACTERS',
    'state_dir' => __DIR__ . '/state',
    'hourly_ip_limit' => 5,
    'hourly_limit' => 40,
    'daily_limit' => 80,
];
