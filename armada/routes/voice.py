"""Authenticated local signaling only; microphone audio never crosses these routes."""
from .. import voice


class VoiceRoutes:
    def _voice_start(self, body):
        try:
            call = voice.start(self.realm, body.get('agent', ''), body.get('thread', 'main'), body.get('sdp'),
                               call_id=body.get('id'), mode=body.get('mode', 'voice'))
            call.changed.wait(45)
            state = call.snapshot(owner=True)
            if not call.sdp:
                call.stop()
                return {'ok': False, 'error': state['error'] or 'Codex voice did not connect. Check Codex sign-in and retry.'}
            return {'ok': True, 'voice': state, 'sdp': call.sdp}
        except (ValueError, OSError) as exc:
            return {'ok': False, 'error': str(exc)}

    def _voice_state(self, body):
        try:
            call = voice.current(self.realm, body.get('agent', ''), body.get('thread', 'main'))
        except (ValueError, OSError) as exc:
            return {'ok': False, 'error': str(exc)}
        if not call or body.get('id') != call.id:
            return {'ok': False, 'error': 'This voice call has ended.'}
        if body.get('heard'):
            call.playback_received(body['heard'])
        if 'mode' in body:
            try:
                call.set_mode(body['mode'])
            except ValueError as exc:
                return {'ok': False, 'error': str(exc)}
        if body.get('played'):
            call.playback_finished(body['played'])
        if body.get('retry'):
            call.retry_playback(body['retry'])
        if body.get('play'):
            try:
                call.play_reply(body['play'])
            except (ValueError, OSError):
                return {'ok': False, 'error': 'Could not play the reply. The full answer is saved in the thread.'}
        return {'ok': True, 'voice': call.snapshot(owner=True)}

    def _voice_stop(self, body):
        try:
            call = voice.current(self.realm, body.get('agent', ''), body.get('thread', 'main'))
        except (ValueError, OSError) as exc:
            return {'ok': False, 'error': str(exc)}
        if call and (not body.get('id') or body['id'] == call.id):
            if body.get('heard'):
                call.playback_received(body['heard'])
            call.stop()
            call.finished.wait(3)
            return {'ok': True, 'voice': call.snapshot(owner=True)}
        return {'ok': True}
