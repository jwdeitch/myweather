import flask
import json
import logging
import logging.handlers
import os
from flask import render_template, request, session
from wunderground import weather_for_url, parse_user_input, jsonify
from os.path import dirname, abspath, isfile
from database import db, Location, Lookup
from datetime import datetime

_DEFAULT_NUM_HOURS = 12
_DEFAULT_UNITS = 'F'
_DEFAULT_USER_INPUT = '10027'

app = flask.Flask(__name__)
SECRET_KEY = os.environ.get('SECRET_KEY', 'development')
API_KEY = os.environ.get('WUNDERGROUND_KEY', 'development')
DEBUG = True if SECRET_KEY == 'development' else False
if not DEBUG:
    import logging
    from TlsSMTPHandler import TlsSMTPHandler
    from email_credentials import email_credentials
    mail_handler = TlsSMTPHandler(*email_credentials())
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)
SQLALCHEMY_DATABASE_URI = 'sqlite:///db.db'
app.config.from_object(__name__)
db.init_app(app)

log = logging.getLogger('seanweather')
log.setLevel(logging.DEBUG)
fh = logging.handlers.RotatingFileHandler('seanweather.log', maxBytes=10000000)
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
log.addHandler(fh)

if not isfile(dirname(abspath(__file__)) + '/db.db'):
    log.warning('db doesnt exist, creating a new one')
    with app.app_context():
        db.create_all()


def main():
    app.run(host='0.0.0.0')


def get_location(user_input):
    ''' first check cache. if missing or too old, use autocomplete API '''
    last_lookup = Lookup.query.filter_by(user_input=user_input).order_by(Lookup.date.desc()).first()
    log.info('db result for location: ' + str(last_lookup))
    if last_lookup is not None and (datetime.now()-last_lookup.date).seconds < 604800:
        log.info('got location info from the cache')
        return last_lookup.location, user_input
    try:
        url, location_name, zmw = parse_user_input(user_input)
        log.info('got location info from autocomplete API')
        log.info('%s -> %s, %s, %s', user_input, url, location_name, zmw)
        return Location(zmw, url=url, name=location_name), user_input
    except IndexError, KeyError:
        flask.flash('seanweather didnt like that, please try another city or zipcode')
        log.warning('failed to parse: %s. Using %s', user_input, _DEFAULT_USER_INPUT)
        last_default = Lookup.query.filter_by(user_input=_DEFAULT_USER_INPUT).order_by(Lookup.date.desc()).first()
        if last_default is not None:
            location = last_default.location
        else:
            url, location_name, zmw = '/q/zmw:10027.1.99999', '10027 - New York, NY', '10027.1.99999'
            location = Location(zmw, url=url, name=location_name)
        return location, _DEFAULT_USER_INPUT


def parse_temps(weather_data, num_hours=24, units=_DEFAULT_UNITS):
    ''' Get current temp, and min/max temps over the next num_hours '''
    temps = []
    key = 'temp_c' if units == 'C' else 'temp'
    for d in weather_data[:num_hours]:
        temps.append(int(d[key]))
    if not temps:
        return '', '', ''
    return temps[0], max(temps), min(temps)


class SeanWeather(object):
    def __init__(self):
        self.data_string = ''
        self.location = None
        self.user_input = _DEFAULT_USER_INPUT
        self.num_hours = _DEFAULT_NUM_HOURS
        self.current_temp = ''
        self.max_temp = ''
        self.min_temp = ''
        self.icon = ''
        self.units = _DEFAULT_UNITS
        self.previous = None

    def update(self):
        log.info('STARTING')
        self.previous = session.get('sw', dict(units=_DEFAULT_UNITS,
            user_input=_DEFAULT_USER_INPUT, num_hours=_DEFAULT_NUM_HOURS))
        self.update_units()
        self.update_location()
        self.update_num_hours()
        self.update_weather_data()
        self.update_current_condtions()
        session['sw'] = dict(units=self.units, user_input=self.user_input,
                num_hours=self.num_hours)
        log.info('FINISHED with %s' % self.user_input)

    def update_units(self):
        self.units = self.previous['units']
        new_units = request.args.get('new_units')
        if new_units in ('C', 'F') and new_units != self.units:
            self.units = new_units
        log.warning('units: %s', self.units)

    def update_location(self):
        user_input = request.args.get('user_input', self.previous['user_input'])
        self.location, self.user_input = get_location(user_input)
        log.info('%s', self.location)

    def update_num_hours(self):
        try:
            self.num_hours = int(request.args.get('num_hours', self.previous['num_hours']))
        except:
            flask.flash('seanweather didnt like the number of hours, using %s', _DEFAULT_NUM_HOURS)
            log.error('bad number of hours')
            self.num_hours = _DEFAULT_NUM_HOURS

    def _was_recently_updated(self, max_seconds=2700):
        return (datetime.now() - self.location.last_updated).seconds <= max_seconds

    def update_weather_data(self):
        if self.location.cache and self._was_recently_updated():
            log.info('weather for %s was recently cached, reusing', self.location.zmw)
        else:
            log.info('using weather API for %s', self.location.zmw)
            wd = weather_for_url(self.location.url, API_KEY)
            self.location.cache = json.dumps(wd)
            if wd:
                self.location.last_updated = datetime.now()
            else:
                log.warning("didn't get any results from weather API")
        self.location = db.session.merge(self.location)
        db.session.add(Lookup(self.user_input, self.location))
        db.session.commit()
        self.weather_data = json.loads(self.location.cache)
        self.data_string = jsonify(self.weather_data[:self.num_hours])

    def update_current_condtions(self):
        self.current_temp, self.max_temp, self.min_temp = \
                parse_temps(self.weather_data, units=self.units)
        self.icon = self.weather_data[0].get('icon') if self.weather_data else ''


@app.before_request
def make_session_permanent():
    session.permanent = True


@app.route('/', methods=['GET'])
def home():
    sw = SeanWeather()
    sw.update()
    return render_template('weather_form.html', sw=sw)


@app.route('/fake')
def fake():
    log.info('STARTING -- fake')
    sw = SeanWeather()
    sw.data_string = '''[{date: new Date(1461434400000),
 icon: 'http://icons.wxug.com/i/c/k/partlycloudy.gif', icon_pos: 100, temp: 66, pop: 15, feel: 66},
{date: new Date(1461438000000),
 icon: 'http://icons.wxug.com/i/c/k/partlycloudy.gif', icon_pos: 100, temp: 67, pop: 15, feel: 67},
{date: new Date(1461441600000),
 icon: 'http://icons.wxug.com/i/c/k/partlycloudy.gif', icon_pos: 100, temp: 67, pop: 15, feel: 67},
{date: new Date(1461445200000),
 icon: 'http://icons.wxug.com/i/c/k/partlycloudy.gif', icon_pos: 100, temp: 68, pop: 15, feel: 68},
{date: new Date(1461448800000),
 icon: 'http://icons.wxug.com/i/c/k/clear.gif', icon_pos: 100, temp: 66, pop: 0, feel: 66},
{date: new Date(1461452400000),
 icon: 'http://icons.wxug.com/i/c/k/clear.gif', icon_pos: 100, temp: 64, pop: 0, feel: 64},
{date: new Date(1461456000000),
 icon: 'http://icons.wxug.com/i/c/k/nt_clear.gif', icon_pos: 100, temp: 62, pop: 0, feel: 62},
{date: new Date(1461459600000),
 icon: 'http://icons.wxug.com/i/c/k/nt_clear.gif', icon_pos: 100, temp: 61, pop: 0, feel: 61},
{date: new Date(1461463200000),
 icon: 'http://icons.wxug.com/i/c/k/nt_clear.gif', icon_pos: 100, temp: 59, pop: 0, feel: 59},
{date: new Date(1461466800000),
 icon: 'http://icons.wxug.com/i/c/k/nt_clear.gif', icon_pos: 100, temp: 58, pop: 0, feel: 58},
{date: new Date(1461470400000),
 icon: 'http://icons.wxug.com/i/c/k/nt_clear.gif', icon_pos: 100, temp: 55, pop: 0, feel: 55},
{date: new Date(1461474000000),
 icon: 'http://icons.wxug.com/i/c/k/nt_clear.gif', icon_pos: 100, temp: 53, pop: 0, feel: 53}]'''
    sw.icon = 'http://icons.wxug.com/i/c/k/nt_clear.gif'
    sw.location = Location('', name='10027 -- New York, NY')
    sw.user_input = 'chilled'
    sw.num_hours = 12
    sw.current_temp, sw.max_temp, sw.min_temp = 75, 80, 65
    log.info('FINISHED with %s -- fake', sw.user_input)
    return render_template('weather_form.html', sw=sw)


@app.route('/discuss')
def discuss():
    return render_template('discuss.html')

if __name__ == '__main__':
    main()
