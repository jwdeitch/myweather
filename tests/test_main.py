import json
import pytest

from app.database import Location, Lookup
import app.main as seanweather

def test_jsonify():
    weather_data = [
    dict(
        date=1498165200000,
        icon="fake_url",
        icon_pos=100,
        pop=0,
        temp=83,
        temp_c=28,
        feel=83,
        feel_c=28),
    dict(
        date=1498168800000,
        icon="fake_url",
        icon_pos=100,
        pop=0,
        temp=81,
        temp_c=27,
        feel=81,
        feel_c=27)
    ]
    actual = seanweather.jsonify(weather_data)
    expected1 = ("{date: new Date(1498165200000), icon: 'fake_url', "
                 "icon_pos: 100, temp: 83, pop: 0, feel: 83, temp_c: 28, "
                 "feel_c: 28}")
    expected2 = ("{date: new Date(1498168800000), icon: 'fake_url', "
                 "icon_pos: 100, temp: 81, pop: 0, feel: 81, temp_c: 27, "
                 "feel_c: 27}")
    expected = '[' + expected1 + ',\n' + expected2 + ']'
    assert actual == expected


@pytest.fixture
def app():
    seanweather.app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite://"
    seanweather.app.config['TESTING'] = True
    return seanweather.app

@pytest.fixture
def db(app):
    seanweather.db.app = app
    seanweather.db.create_all()
    yield seanweather.db
    seanweather.db.drop_all()

@pytest.fixture(scope='function')
def session(db):
    connection = db.engine.connect()
    transaction = connection.begin()
    db.session = db.create_scoped_session(options=dict(bind=connection))

    yield db.session

    transaction.rollback()
    connection.close()
    db.session.remove()


def _add_lookup(session, user_input='', url='', name='', cache=''):
    location = session.merge(Location(url, name, cache=cache))
    session.add(Lookup(user_input, location))
    session.commit()


########## SeanWeather.update_location ##############

# def test_update_location_lookup_table(app, session):
#     _add_lookup(session, user_input='New York', url='/q/nyc',
#                 name='New York, New York')
#     sw = seanweather.SeanWeather()
#     sw.previous = seanweather.CookieData(units='F', user_input='', num_hours=0)
#     with app.test_request_context('?user_input=New+York'):
#         sw.update_location(opener=None)
#     assert sw.location.name == 'New York, New York'
#     assert sw.user_input == 'New York'

PARIS_JSON = json.dumps({"RESULTS": [
    {
        "name": "Paris, France",
        "type": "city",
        "c": "FR",
        "zmw": "00000.45.07156",
        "tz": "Europe / Paris",
        "tzs": "CET",
        "l": "/q/zmw:00000.45.07156",
        "ll": "48.860001 2.350000",
        "lat": "48.860001",
        "lon": "2.350000"
    },
]})

# def test_update_location_autocomplete_new(app, session):
#     ''' The user input isn't in the (empty) Lookup table, so it checks
#         the autocomplete API instead, which returns some json for Paris.
#         Paris isn't in the Location table so it returns a new Location built
#         from the Paris json.
#     '''
#     sw = seanweather.SeanWeather()
#     sw.previous = seanweather.CookieData(units='F', user_input='', num_hours=0)
#     def opener(url):
#         def inner():
#             pass
#         inner.read = lambda: PARIS_JSON
#         return inner
#     fake_user_input = 'fake user input'
#     with app.test_request_context('?user_input=%s' % fake_user_input):
#         sw.update_location(opener)
#     assert sw.location.name == 'Paris, France'
#     assert sw.user_input == fake_user_input

# def test_update_location_autocomplete_reuse(app, session):
#     ''' The user input isn't in the (empty) Lookup table, so it checks the
#         autocomplete API instead, which returns some json for Paris. The url
#         from that json *is* in the Location table so it returns that Location
#         and ignores the Paris json.
#     '''
#     sw = seanweather.SeanWeather()
#     sw.previous = seanweather.CookieData(units='F', user_input='', num_hours=0)
#     def opener(url):
#         def inner():
#             pass
#         inner.read = lambda: PARIS_JSON
#         return inner
#     fake_user_input = 'fake user input'
#     fake_location_name = 'Fake Paris'
#     real_paris_url = '/q/zmw:00000.45.07156' # compare this to the paris JSON above
#     _add_lookup(session, user_input=fake_user_input, url=real_paris_url,
#         name=fake_location_name)

#     with app.test_request_context('?user_input=%s' % fake_user_input):
#         sw.update_location(opener)
#     assert sw.location.name == fake_location_name
#     assert sw.user_input == fake_user_input

# def test_update_location_default_nocache(app, session):
#     ''' The autocomplete API returns nothing and raises an IndexError. With nothing
#         in the database, it returns the default location with no cache.
#     '''
#     sw = seanweather.SeanWeather()
#     sw.previous = seanweather.CookieData(units='F', user_input='', num_hours=0)
#     with app.test_request_context('?user_input=Boston'):
#         sw.update_location(opener=lambda url: [][0])
#     assert sw.location.name == seanweather._DEFAULT_LOCATION_NAME
#     assert sw.user_input == seanweather._DEFAULT_USER_INPUT
#     assert sw.location.cache == ''

# def test_update_location_default_cache(app, session):
#     ''' The autocomplete API returns nothing and raises an IndexError. But there is
#         an entry for the default Location in the db, so it returns that (with its cache)
#     '''
#     sw = seanweather.SeanWeather()
#     sw.previous = seanweather.CookieData(units='F', user_input='', num_hours=0)
#     cache = 'old weather data'
#     _add_lookup(session, user_input='New York', url=seanweather._DEFAULT_LOCATION_URL,
#         name=seanweather._DEFAULT_LOCATION_NAME, cache=cache)
#     with app.test_request_context('?user_input=Boston'):
#         sw.update_location(opener=lambda url: [][0])
#     assert sw.location.name == seanweather._DEFAULT_LOCATION_NAME
#     assert sw.user_input == seanweather._DEFAULT_USER_INPUT
#     assert sw.location.cache == cache


########## SeanWeather.update_units ##############

def test_update_units_no_request(app):
    sw = seanweather.SeanWeather()
    sw.previous = seanweather.CookieData(units='C', user_input='', num_hours=0)
    with app.test_request_context(''):
        sw.update_units()
    assert sw.units == seanweather.Units.C

def test_update_units_request_invalid(app):
    ''' The new_units query parameter is often missing '''
    sw = seanweather.SeanWeather()
    sw.previous = seanweather.CookieData(units='C', user_input='', num_hours=0)
    with app.test_request_context('?new_units=&num_hours=24'):
        sw.update_units()
    assert sw.units == seanweather.Units.C

def test_update_units_request_same(app):
    sw = seanweather.SeanWeather()
    sw.previous = seanweather.CookieData(units='C', user_input='', num_hours=0)
    with app.test_request_context('?new_units=C'):
        sw.update_units()
    assert sw.units == seanweather.Units.C

def test_update_units_request_new(app):
    sw = seanweather.SeanWeather()
    sw.previous = seanweather.CookieData(units='C', user_input='', num_hours=0)
    with app.test_request_context('?new_units=F'):
        sw.update_units()
    assert sw.units == seanweather.Units.F


########## SeanWeather.update_num_hours ##############

def test_update_num_hours_bad_request(app):
    sw = seanweather.SeanWeather()
    sw.previous = seanweather.CookieData(units='', user_input='', num_hours='36')
    with app.test_request_context('?num_hours=tacos'):
        sw.update_num_hours()
    assert sw.num_hours == seanweather._DEFAULT_NUM_HOURS

def test_update_num_hours_good_request(app):
    sw = seanweather.SeanWeather()
    sw.previous = seanweather.CookieData(units='', user_input='', num_hours='36')
    with app.test_request_context('?num_hours=48'):
        sw.update_num_hours()
    assert sw.num_hours == 48


########## SeanWeather.update_weather_data ##############

# def test_update_weather_data_cached(session):
#     sw = seanweather.SeanWeather()
#     weather_data = [dict(date=0, icon='', icon_pos=100, temp='100', pop='0',
#                          feel='100', temp_c='35', feel_c='35')]*100
#     sw.location = Location('url', name='NYC', cache=json.dumps(weather_data))
#     sw.update_weather_data(weather_getter=lambda url, api_key: [])
#     assert sw.weather_data == weather_data

def test_update_weather_data_not_cached_empty_response(session):
    sw = seanweather.SeanWeather()
    sw.location = Location('url', name='NYC')
    sw.update_weather_data(weather_getter=lambda url, api_key: [])
    assert sw.weather_data == []

def test_update_weather_data_not_cached_good_response(session):
    sw = seanweather.SeanWeather()
    sw.location = Location('url', name='NYC')
    weather_data = [dict(date=0, icon='', icon_pos=100, temp='100', pop='0',
                         feel='100', temp_c='35', feel_c='35')]*100
    sw.update_weather_data(weather_getter=lambda url, api_key: weather_data)
    assert sw.weather_data == weather_data


########## SeanWeather.update_current_conditions ##############

def _get_weather_data():
    weather_data = [{'temp': '83', 'temp_c': '28', 'icon': 'cloud'},
                    {'temp': '81', 'temp_c': '27', 'icon': 'sun'},
                    {'temp': '85', 'temp_c': '29'}]
    weather_data *= 10
    # The below two data points are outside the default 24-hour period, so they
    # should not be included in the max/min calculation
    weather_data.append({'temp': '100', 'temp_c': '100'})
    weather_data.append({'temp': '0', 'temp_c': '0'})
    return weather_data

def test_update_current_conditions_F():
    sw = seanweather.SeanWeather()
    sw.weather_data = _get_weather_data()

    sw.update_current_conditions()

    assert sw.current_temp == 83
    assert sw.max_temp == 85
    assert sw.min_temp == 81
    assert sw.icon == 'cloud'

def test_update_current_conditions_C():
    sw = seanweather.SeanWeather()
    sw.units = seanweather.Units.C
    sw.weather_data = _get_weather_data()

    sw.update_current_conditions()

    assert sw.current_temp == 28
    assert sw.max_temp == 29
    assert sw.min_temp == 27
    assert sw.icon == 'cloud'
