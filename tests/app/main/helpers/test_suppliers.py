import pytest
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import Length
from app.main.helpers.suppliers import get_country_name_from_country_code, supplier_company_details_are_complete

from dmutils.api_stubs import supplier


class TestGetCountryNameFromCountryCode:
    @pytest.mark.parametrize(
        'code, name',
        (
            ('gb', 'United Kingdom'),
            ('country:GB', 'United Kingdom'),
            ('territory:UM-86', 'Jarvis Island'),
            (None, ''),
            ('notathing', ''),
        )
    )
    def test_returns_expected_name_for_different_codes(self, code, name):
        assert get_country_name_from_country_code(code) == name


class TestSupplierCompanyDetailsComplete:
    @pytest.mark.parametrize('supplier_data_from_api, expected_result',
                             (
                                 ({}, False),
                                 ({**supplier()['suppliers'], 'dunsNumber': None}, False),
                                 ({**supplier()['suppliers'], 'vatNumber': None}, False),
                                 ({**supplier()['suppliers'], 'companiesHouseNumber': None}, False),
                                 ({**supplier()['suppliers'], 'contactInformation': [{}]}, False),

                                 (supplier()['suppliers'], True),
                                 ({**supplier()['suppliers'], 'registrationCountry': 'gb'}, True),
                                 (supplier(other_company_registration_number=12345)['suppliers'], True),
                             ))
    def test_returns_expected_value_for_input(self, supplier_data_from_api, expected_result):
        assert supplier_company_details_are_complete(supplier_data_from_api) is expected_result


class FormForTest(FlaskForm):
    field_one = StringField('Field one?', validators=[
        Length(max=5, message="Field one must be under 5 characters.")
    ])
    field_two = StringField('Field two?', validators=[
        Length(max=5, message="Field two must be under 5 characters.")
    ])
    field_three = StringField('Field three?', validators=[
        Length(max=5, message="Field three must be under 5 characters.")
    ])
