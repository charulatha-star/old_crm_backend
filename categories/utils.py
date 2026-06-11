# Email sending utility


from email.mime.image import MIMEImage
from django.core.mail import get_connection, EmailMultiAlternatives
from django.template import loader

# Email connection 
def get_email_connection(my_username="jegatheeshwaran@billiontags.com", my_password="Jeganeswaran1993"):
    smtp_host = 'smtp.gmail.com'
    smtp_port = 587
    smtp_use_tls = True
    connection = get_connection(host=smtp_host, port=smtp_port, username=my_username, password=my_password,
                                use_tls=smtp_use_tls)
    return connection

# Send email function 
def send_email(to_email, context, subject_template_name,
               plain_body_template_name=None, html_body_template_name=None, bcc_email=None, cc_email=None):
    import pdb
    pdb.set_trace()   # pdb.set_trace() is a Python debugger breakpoint

    assert plain_body_template_name or html_body_template_name
    subject = loader.render_to_string(subject_template_name, context)
    subject = ''.join(subject.splitlines())

    html_body = loader.render_to_string(html_body_template_name, context)

    connection = get_email_connection()
    from_email = "jegatheeshwaran@billiontags.com"

    if not isinstance(to_email, list):
        to_email = [to_email]

    if not isinstance(bcc_email, list):
        if bcc_email:
            bcc_email = [bcc_email]
        else:
            bcc_email = []

    if not isinstance(cc_email, list):
        if cc_email:
            cc_email = [cc_email]
        else:
            cc_email = []

    email_message = EmailMultiAlternatives(subject, "", from_email, to_email, bcc=bcc_email, cc=cc_email,
                                           connection=connection)

    if "project" in context and context['project']:
        if context['project'].logo:
            image = MIMEImage(context['project'].logo.read())
            image.add_header('Content-ID', '<{}>'.format(context['project'].logo))
            email_message.attach(image)

        for image in context['project'].project_images.all():
            with open(image.image.path, 'rb') as image_fd:
                mime_image = MIMEImage(image_fd.read(), _subtype="jpeg")
                mime_image.add_header('Content-ID', '<{}>'.format(image.image))
                email_message.attach(mime_image)

    email_message.attach_alternative(html_body, "text/html")
    email_message.send()
    print("email send..")

# Helper functions (used for password reset links)
def encode_uid(pk):            # converts user ID to base64 URL-safe string
    try:
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        return urlsafe_base64_encode(force_bytes(pk)).decode()
    except ImportError:
        from django.utils.http import int_to_base36
        return int_to_base36(pk)


def decode_uid(pk):     # reverses it back to ID
    try:
        from django.utils.http import urlsafe_base64_decode
        from django.utils.encoding import force_text
        return force_text(urlsafe_base64_decode(pk))
    except ImportError:
        from django.utils.http import base36_to_int
        return base36_to_int(pk)


class SendEmailViewMixin(object):
    token_generator = None
    subject_template_name = None
    plain_body_template_name = None
    html_body_template_name = None

    def __init__(self):
        self.request = None

    def send_email(self, to_email, context):
        send_email(to_email, context, **self.get_send_email_extras())

    def get_send_email_extras(self):
        return {
            'subject_template_name': self.get_subject_template_name(),
            'plain_body_template_name': self.get_plain_body_template_name(),
            'html_body_template_name': self.get_html_body_template_name(),
        }

    def get_subject_template_name(self):
        return self.subject_template_name

    def get_plain_body_template_name(self):
        return self.plain_body_template_name

    def get_html_body_template_name(self):
        return self.html_body_template_name

    def get_send_email_kwargs(self, user):
        return {
            'to_email': user.email,
            'context': self.get_email_context(user),
        }

    def get_email_context(self, user):
        uid = user.pk
        return {
            'user': user,
            'uid': uid,
            "token": ""
        }

