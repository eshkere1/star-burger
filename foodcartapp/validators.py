import phonenumbers
from django.core.exceptions import ValidationError


def validate_phonenumber(value):
    """Проверить, что это настоящий телефонный номер.

    Валидатор висит на самом поле модели, поэтому одинаково срабатывает и в
    API, и в форме менеджера, и в админке — проверку не нужно повторять в
    каждой из них.
    """
    try:
        parsed_number = phonenumbers.parse(value, 'RU')
    except phonenumbers.NumberParseException:
        raise ValidationError('Введен некорректный номер телефона')

    if not phonenumbers.is_valid_number(parsed_number):
        raise ValidationError('Введен некорректный номер телефона')
