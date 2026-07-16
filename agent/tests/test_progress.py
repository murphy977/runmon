from runmon.progress import ProgressParser, parse_eta


def test_parse_eta():
    assert parse_eta("04:05") == 245
    assert parse_eta("1:02:03") == 3723
    assert parse_eta("??") is None


def test_tqdm_line():
    p = ProgressParser()
    changed = p.feed(" 45%|████▌     | 450/1000 [03:20<04:05,  2.24it/s]")
    assert changed and p.state.percent == 45.0 and p.state.eta_seconds == 245


def test_epoch_and_loss():
    p = ProgressParser()
    p.feed("Epoch 3/10\nstep 100 loss=0.4321 lr=1e-4")
    assert p.state.epoch == (3, 10) and p.state.loss == 0.4321


def test_carriage_return_stream():
    p = ProgressParser()
    p.feed("10%|█| 10/100 [00:01<00:09, 10.0it/s]\r20%|██| 20/100 [00:02<00:08, 10.0it/s]")
    assert p.state.percent == 20.0


def test_scientific_loss_and_no_match():
    p = ProgressParser()
    assert p.feed("loss: 3.5e-05") and p.state.loss == 3.5e-05
    assert not p.feed("nothing to see here")
