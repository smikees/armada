# ARMADA report relay

The desktop keeps **Send report**. Its only mail request is HTTPS to
`https://armada.stamih.com/api/report.php`, carrying the approved report and a random request ID.
The relay sends through Resend to `armada@stamih.com`; no caller can select a recipient or sender.
No mail credential belongs in the desktop package, update ZIP, Git, or public web directory.

## Hosting setup

Requires PHP 8.1 or later with cURL, HTTPS to Resend, and a writable private local directory.

1. Create a directory outside **every** website document root on the hosting account, for example
   `/home/ACCOUNT/armada-reports`. Set directory permissions to 0700. Put `relay.php` there.
2. Copy `config.example.php` there as `config.php` and restrict it to 0600. Enter a new Resend
   sending-only key restricted to the ARMADA sending domain, and at least 32 random characters
   for `rate_salt`. Create its `state/` directory with permissions 0700. Never copy that configured
   file into this repository. Mihai confirmed deletion of the previously distributed beta key.
3. Set `ARMADA_REPORT_PRIVATE` in the hosting PHP environment to the private directory, or set
   the nonsecret absolute path in the public `report.php` entry point. Upload only that entry
   point to the website's `/api/report.php`. The library and configuration stay outside the web root.
4. Confirm the public route runs PHP and does not return source. Verify config/library/state
   cannot be requested through any domain on the account. Invalid input must not send email.
5. Send one explicitly approved test report, check arrival, repeat the same ID and verify there
   is only one email. Verify the installed client's preview and Send report flow afterward.

Deployed on 3 October 2026 to PHP 8.3 hosting. The approved verification email was accepted
by Resend and Mihai confirmed its arrival. Live checks verified recipient/size restrictions,
private URLs returning 404, and identical-request deduplication. Temporary installers were
removed. Final installer/client rehearsal is tracked under R7 in the public-readiness review.
The static website deployment procedure must not upload this entire directory. Keep backups
and certificate-verified FTPS.

## Abuse limits and recovery

Defaults allow five requests per IP per hour, 40 globally per hour, and 80 new reports per rolling
24 hours. Rates apply on the server, independent of client code. A fixed global budget bounds
abuse even from many IPs; abuse can still exhaust availability, so review hosting access logs and
adjust limits as real usage warrants. Client secrets would not solve that problem.

Only hashed IP identifiers, payload hashes, request IDs and delivery status are persisted, for
24 hours; report bodies and mail credentials are not logged. The host may separately retain
ordinary HTTP access logs. `REMOTE_ADDR` is used directly: configure any trusted reverse proxy
at the web-server layer, never trust arbitrary forwarded-IP headers in PHP.

A stable file lock covers quota reservation and delivery. Damaged state returns 503 and is
preserved. The client saves a local copy on failure and retains its preview for a safe retry.
The same request ID and payload reuse a Resend idempotency key, including after a lost response.
[Resend documents a 24-hour idempotency window](https://resend.com/docs/dashboard/emails/idempotency-keys);
the client's preview expires after 30 minutes. No automatic bulk retry or redelivery job exists.

## Local tests

Run `php support-relay/test.php <new-disposable-directory>` from the repository root. Tests inject
a delivery function and exercise fixed-recipient validation, byte limits, invalid input, replay,
quota limits, locking, uncertain delivery and damaged state. No mail is sent by these tests.
