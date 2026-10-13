from judgment.contracts import SOURCE_COMMIT


class FakeBackend:
    """합성 tokenizer 대역. 실제 tokenizer 호환성 증거가 아니다."""
    source_commit = SOURCE_COMMIT
    model_revision = 'fixture-only'
    head_limit = 10000
    total_limit = 20000

    def __init__(self, *, truncate=False, collision=False, lost_context=False):
        self.truncate, self.collision, self.lost_context = truncate, collision, lost_context
        self.calls = 0

    def prepare(self, rendered):
        options = [tuple(map(ord, cid + ': ' + desc)) for cid, desc in rendered['question']['criteria'].items()]
        head = tuple(map(ord, rendered['question']['instructions']))
        actual = [o[:-1] for o in options] if self.truncate else options[:]
        if self.collision: actual[1] = actual[0]
        state = tuple(map(ord, rendered['state']))
        return dict(original_options=options, actual_options=actual, original_head=head, actual_head=head,
                    original_state=state, actual_state=state[:-1] if self.lost_context else state,
                    head_tokens=len(head) + sum(map(len, options)), total_tokens=len(head) + sum(map(len, options)) + len(state))

    def raw_logits(self, prepared):
        self.calls += 1
        return tuple(float(i) for i in range(len(prepared['original_options'])))
