# coding: utf-8

from django.dispatch import Signal

__all__ = [
    'post_email_confirmation_send',
    'post_email_confirmation_confirm',
    'logined_but_required_email_confirm'
]

"""
Signal arguments: user_obj
"""
logined_but_required_email_confirm = Signal()

"""
Signal arguments: confirmation
"""
post_email_confirmation_send = Signal()

"""
Signal arguments: confirmation, save_to_content_object, old_email
"""
post_email_confirmation_confirm = Signal()