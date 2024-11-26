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
        'required': False,  
        'default': None
    },
    'start': {
        'type': float,
        'required': False, 
        'default': None
    },
    'end': {
        'type': float,
        'required': False, 
        'default': None
    },
    'subtitles': {
        'type': str,
        'required': False,
        'default': None 
    },
    'batch': {
        'type': list,
        'required': False,  
        'default': [],
        'schema': {
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
                'required': True,
                'default': '' 
            },
        }
    }
}
