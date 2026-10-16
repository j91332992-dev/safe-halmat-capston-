from app.services.anchor_transition_guard import AnchorTransitionGuard


def test_one_missing_anchor_does_not_move_then_recovers_immediately():
    g=AnchorTransitionGuard()
    assert g.check('tag','s',[1,2,3,4],2,2,0)['accepted']
    assert not g.check('tag','s',[2,3,4],2,3,.3)['accepted']
    assert g.check('tag','s',[1,2,3,4],2,2,.6)['accepted']


def test_persistent_change_is_not_frozen_forever():
    g=AnchorTransitionGuard();g.check('t','s',[1,2,3,4],0,0,0)
    assert not g.check('t','s',[2,3,4],0,1,.3)['accepted']
    assert not g.check('t','s',[2,3,4],0,1,.6)['accepted']
    assert g.check('t','s',[2,3,4],0,1,.9)['accepted']


def test_motion_with_same_anchors_is_not_delayed():
    g=AnchorTransitionGuard();g.check('t','s',[1,2,3,4],0,0,0)
    assert g.check('t','s',[1,2,3,4],1,0,.3)['accepted']


def test_new_session_resets_reference():
    g=AnchorTransitionGuard();g.check('t','s',[1,2,3,4],0,0,0)
    assert g.check('t','s2',[2,3,4],0,1,.3)['accepted']
