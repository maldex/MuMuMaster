# -*- coding: utf-8 -*-
import simplejson as json
from glob import glob
from globals import *
from MuMuStation import MuMuStation
from MuMuTuner import MuMuTuner


class MuMuMaster():
    def __init__(self, configs = []):

        if len(configs) == 0:
            configs = glob('config/tuner.*.json')

        self.tuners = []
        self.stations = []
        for cfg in configs:
            with open(cfg, 'r') as f:
                tc = json.loads(f.read())

            t_instance = MuMuTuner(host=tc['ssh_host'],
                                   user=tc['ssh_user'],
                                   password=tc['ssh_pass'],
                                   port=tc['ssh_port'],
                                   tuner=tc['tuner'],
                                   http_port=tc['http_port'],
                                   http_prefix=tc['http_prefix'])

            self.tuners.append(t_instance)

            with open(tc['station_cfg'],'r') as f:
                stations = json.loads(f.read())

            for s in stations:
                s_instance = MuMuStation()
                s_instance.deserialize(s)
                s_instance.set_tuner(t_instance)
                self.stations.append(s_instance)

        MyLogger.info('loaded ' + str(len(self.tuners)) + ' tuners and ' + str(len(self.stations)) + ' stations')

    def get_tuner_configs(self):
        r = []
        for t in self.tuners:
            r.append(t.get_current_config())
        return r


    def already_tuned(self, station):
        assert isinstance(station, MuMuStation)
        for t in self.tuners:
            if t.get_status() < MuMuTuner.STATUS_AUTOCONFIG:
                continue
            config = t.get_current_config()
            if config['freq'] == station.freq and station.sid in config['sids']:
                return True
        return False

    def get_302_url(self, station):
        assert isinstance(station, MuMuStation)
        tuner = station.get_tuner()
        assert isinstance(tuner, MuMuTuner)
        return tuner._http_prefix + '/bysid/' + str(station.sid)

    def get_302(self,station):
        return "Status: 302 Moved\nLocation: " + self.get_302_url(station) + "\n\n";

    def get_404(self, station):
        return "Status: 404 Not Found\n";

    def get_500(self, station):
        return "Status: 500 Internal Server Error\n";

    def get_station_by_name(self, name):
        for s in self.stations:
            if s.title.lower() == name.lower():
                return s
        return None

    def get_station_by_sid(self, sid, freq):
        for s in self.stations:
            if s.sid == sid and s.freq == freq:
                return s
        return None

    def get_current_stations(self):
        cc = self.get_tuner_configs()
        r = []
        for t in cc:
            if t.has_key('sids'):
                for s in t['sids']:
                    station = self.get_station_by_sid(s, t['freq'])
                    if station is not None:
                        r.append(station)
        return r

    def get_same_sids(self, station):
        assert isinstance(station, MuMuStation)
        r = [station.sid]
        c = ['Station List']
        for s in self.stations:
            if station.freq == s.freq and station == s:
                r.append(s.sid)
                c.append(str(s.sid) + ' - ' + s.title)
        r = list(set(r)) # somehow it's not unque
        c = list(set(c)) # somehow it's not unque
        return r,c


    def tune_to(self, station):
        if not isinstance(station, MuMuStation):
            MyLogger.debug("looking up '" + station + "'")
            station = self.get_station_by_name(station)
            if not isinstance(station, MuMuStation):
                MyLogger.warn("not found")
                return self.get_404(station)

        MyLogger.debug('tuning to ' + station.title)
        tuner = station.get_tuner()

        MyLogger.debug("found on tuner '" + tuner.tuner + "' on host '" + tuner.ssh.host + "' with sid " + str(
            station.sid) + "/" + str(station.freq))

        if not self.already_tuned(station):
            sids, comment = self.get_same_sids(station)
            MyLogger.info('not yet available, tuning to ' + str(station.freq) + ' with sids ' + str(sids))
            assert isinstance(tuner, MuMuTuner)
            if not station.is_dvbs():
                tuner.set_config(station.freq, sids=sids, comment_list=comment)
            else:
                tuner.set_config(freq=station.freq, sids=sids,
                                 pol=station.dvbs['pol'],
                                 srate=station.dvbs['srate'],
                                 diseqc=station.dvbs['diseqc'],
                                 comment_list=comment)
            if not tuner.start():
                return self.get_302(station)
                quit()
        else:
            MyLogger.info('already tuned')

        return self.get_302(station)

