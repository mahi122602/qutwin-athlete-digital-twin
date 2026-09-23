"""Keep event assignments attached to their records through chronological sorting."""
EVENTS = {'100 m','200 m','400 m','800 m','1500 m','5 km','10 km','Half Marathon','Marathon'}


def attach_events(frame, assignments):
    mapping = {}
    for item in assignments:
        position = int(item['record'])
        if position in mapping or item['event'] not in EVENTS:
            raise ValueError('Each record must have one valid event assignment.')
        mapping[position] = item['event']
    if set(mapping) != set(range(1, len(frame)+1)):
        raise ValueError('Assign an event to every exercise record before processing.')
    result = frame.copy()
    result['event_type'] = [mapping[i] for i in range(1,len(frame)+1)]
    return result


def describe_event_context(frame):
    result = frame.copy()
    # Explicit context only: event-specific numerical models are not trained.
    for index, row in result.iterrows():
        event = row.get('event_type')
        if event in EVENTS:
            original = str(row.get('recommendation') or '')
            result.at[index,'recommendation'] = (
                f'{original} Event context: {event}. Review this result alongside your '
                f'{event} session plan; the numeric scores are not event-adjusted.'
            )
    return result
