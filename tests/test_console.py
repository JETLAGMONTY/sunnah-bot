import console


def run(capsys, *args):
    console.main(list(args))
    return capsys.readouterr().out


def test_console_answers_commands_from_fixtures(capsys):
    out = run(capsys, "--now", "2026-09-04T12:00+01:00", "/city Bristol", "/times")
    assert "Prayer times — Bristol, England, United Kingdom" in out and "← next" in out


def test_console_clock_steps_run_the_scheduler(capsys):
    out = run(capsys, "--now", "2026-09-04T12:00+01:00", "/city Bristol", "@2026-09-04T18:50+01:00")
    assert "The last hour before Maghrib (Friday)" in out


def test_console_shares_a_location(capsys):
    out = run(capsys, "--now", "2026-06-20T12:00+00:00", "loc:64.1466,-21.9426", "/times")
    assert "(+1)" in out
