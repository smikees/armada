# `armada/capability_reviews.py`

Durable, realm-scoped reviews. Navigation never owns a review's lifetime.

Only a verified source fingerprint can reuse a report. Restoring a report does not
run the reviewer; explicitly reviewing again verifies the version first.

### `_hash(value)`

—

### `_directory(root)`

—

### `github_repo(url)`

Recognize a repository link, never a lookalike host or arbitrary search prose.

### `_version(url, key)`

—

### `local_review(key)`

—

### `start(root, url='', key='')`

—

### `_run(directory, row, task)`

—

### `recent(root)`

—
