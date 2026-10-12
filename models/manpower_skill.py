from odoo import fields, models


class ManpowerSkill(models.Model):
    _name = 'manpower.skill'
    _description = 'Manpower Skill'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
