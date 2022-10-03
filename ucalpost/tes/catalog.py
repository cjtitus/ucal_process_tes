import mass
from mass.off import getOffFileListFromOneFile as getOffList
import os
from os import path
from ucalpost.tes.calibration import _calibrate
from ucalpost.databroker.run import get_tes_state, get_line_names, get_filename
from ucalpost.tes.process_routines import get_analyzed_filename


class CatalogData:
    def __init__(self, cal_runs, data_runs, savenames=None):
        """
        off_filename : Full path to one .off file, from which the others will be found
        cal_states : states in the .off file that should be used for calibration
        data_states : states in the .off file that are data
        savenames: A dictionary mapping state names to savefile names
        """
        self.cal_runs = cal_runs
        self.data_runs = data_runs
        self.cal_states = [get_tes_state(cal) for cal in self.cal_runs]
        self.data_states = [get_tes_state(d) for d in self.data_runs]
        allruns = cal_runs + data_runs
        self.off_filename = get_filename(allruns[0])
        if savenames is None:
            self.savenames = {}
            for run in allruns:
                savename = get_analyzed_filename(run)
                state = get_tes_state(run)
                self.savenames[state] = savename
        else:
            self.savenames = savenames
        self.data = mass.off.ChannelGroup(getOffList(self.off_filename)[:1000])
        self.ds = self.data.firstGoodChannel()

    @property
    def driftCorrected(self):
        try:
            return hasattr(self.ds, "filtValueDC")
        except:
            return False


def driftCorrect(catalog, states=None, redo=False):
    """
    catalog : A CatalogData instance
    states : Optional, a list of states to use for DC
    """
    if states is None:
        states = catalog.cal_states + catalog.data_states
    if not catalog.driftCorrected or redo:
        print("Drift Correcting")
        catalog.data.learnDriftCorrection(states=states)
    else:
        print("Drift Correction already done")


def calibrate(catalog, states=None, attr=None, stateOptions={}, rms_cutoff=0.2,
              save=True, saveSummary=True):
    cal_md = {}
    if states is None:
        states = catalog.cal_states
    if attr is None:
        attr = 'filtValueDC' if catalog.driftCorrected else 'filtValue'
    cal_md['states'] = states
    cal_md['attr'] = attr
    for c in catalog.cal_runs:
        state = get_tes_state(c)
        line_names = get_line_names(c)
        opt = stateOptions.get(state, {})
        if 'savefile' not in opt:
            savebase = "_".join(path.basename(catalog.off_filename).split('_')[:-1])
            savefile = f"{savebase}_{state}_cal.hdf5"
        else:
            savefile = opt['savefile']
        _calibrate(catalog.data, state, line_names, fv=attr, rms_cutoff=rms_cutoff)
        if save:
            if not path.exists(path.dirname(savefile)):
                os.makedirs(path.dirname(savefile))
            catalog.data.calibrationSaveToHDF5Simple(savefile)
    catalog.cal_md = cal_md


def summarize_calibration(catalog, state, savedir=None):
    if savedir is not None:
        if not os.path.exists(savedir):
            os.makedirs(savedir)
    
