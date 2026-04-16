from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.widgets import SwitchWidget
from wtforms import BooleanField


class SettingsForm(IndicoForm):
    """Plugin settings form."""

    enabled = BooleanField(
        _('Enable registration form prefilling'),
        widget=SwitchWidget(),
        description=_(
            'Automatically prefill custom registration form fields with data '
            "from the user's most recent completed registration. Fields are "
            'matched by internal name and field type across all events.'
        )
    )
