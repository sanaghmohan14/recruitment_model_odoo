{
    'name': 'Client Manpower Requisition & Job Openings',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'author': 'Custom',
    'summary': 'Client manpower requirements with Dept Head -> Project Manager -> CEO approval -> HR',
    'description': """
Standalone manpower requisition module (independent of hr_recruitment).

Workflow: Dept Head creates hiring request -> Project Manager reviews -> CEO approves -> HR creates and publishes Job Opening.
    """,
    'depends': ['base', 'mail', 'hr', 'website', 'project'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/channel_data.xml',
        'views/project_task_views.xml',
        'views/requirement_views.xml',
        'views/job_opening_views.xml',
        'views/application_views.xml',
        'views/application_email_wizard_views.xml',
        'views/application_reject_wizard_views.xml',
        'views/requirement_reject_wizard_views.xml',
        'views/requirement_client_wizard_views.xml',
        'views/application_client_wizard_views.xml',
        'views/menus.xml',
        'views/website_job_opening_templates.xml',
        'views/website_requirement_templates.xml',
    ],
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
