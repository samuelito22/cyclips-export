INPUT_VALIDATIONS = {
    'task': {
        'type': str,
        'required': True,
        'default': None
    },
    'video_url': {
        'type': str,
        'required': True,
        'default': None
    },
    'scenes_url': {
        'type': str,
        'required': True,
        'default': None
    },
    'destination_url': {
        'type': str,
        'required': True,
        'default': ''
    },
    'start': {
        'type': float,
        'required': True,
        'default': 0
    },
    'end': {
        'type': float,
        'required': True,
        'default': 0
    },
    'subtitles': {
        'type': str,
        'required': False,
        'default': ''
    },
}
