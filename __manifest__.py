{
    'name': 'Client Manpower Requisition & Job Openings',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Client manpower requirements with Dept Head -> HR -> CEO approval and job openings',
    'description': """
Standalone manpower requisition module (independent of hr_recruitment).

Workflow: Dept Head registers the client's requirement -> HR reviews experience/salary
-> CEO approves -> HR creates and publishes a Job Opening.
    """,
    'depends': ['base', 'mail', 'hr'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/channel_data.xml',
        'views/requirement_views.xml',
        'views/job_opening_views.xml',
        'views/menus.xml',
    ],
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
