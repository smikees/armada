"""Display schedules without leaking cron syntax or changing execution semantics."""
import pytest
from armada.webui.schedfmt import _humanize


@pytest.mark.parametrize('schedule,label', [
    ('*/15 15-16 * * 1-5', 'weekdays every 15 min, 15:00–16:45'),
    ('* * * * *', 'daily every minute'),
    ('*/15 * * * *', 'daily every 15 min'),
    ('0 */2 * * *', 'daily every 2 hours'),
    ('15 * * * *', 'daily hourly at :15'),
    ('30 9-17 * * mon-fri', 'weekdays hourly, 09:30–17:30'),
    ('0 9,17 * * 1,3,5', 'Mon, Wed, Fri 09:00, 17:00'),
    ('45 19 * * 1-5', 'weekdays 19:45'),
    ('0 8 * * sat#1', '1st Sat 08:00'),
    ('0 8 1-7 * 6', 'days 1–7 or Sat 08:00'),
    ('0 11 1 1,4,7,10 *', '1st in Jan, Apr, Jul, Oct 11:00'),
    ('0 11 * jan-mar mon', 'Mon in Jan–Mar 11:00'),
    ('0 8 * * 0,6', 'weekends 08:00'),
    ('mon-fri 14:00', 'weekdays 14:00'),
    ('manual', 'on demand'),
    ('daily 09:30', 'daily 09:30'),
    ('0 nope * * *', 'Schedule needs review'),
    ('*/0 * * * *', 'Schedule needs review'),
])
def test_readable_exact_schedule(schedule, label):
    assert _humanize(schedule) == label


@pytest.mark.parametrize('schedule', ['*/7 9,12,15 * * 1-5', '1,7,17 8-18/2 1,15 */3 *'])
def test_irregular_fields_still_have_readable_labels(schedule):
    label = _humanize(schedule)
    assert '*' not in label and '/' not in label
    assert 'minutes' in label and 'hours' in label
