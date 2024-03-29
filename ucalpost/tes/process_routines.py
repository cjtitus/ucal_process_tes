import numpy as np
from ..databroker.run import (
    get_filename,
    get_cal,
    get_tes_state,
    get_line_names,
    get_save_directory,
    get_cal_id,
)
from .raw_classes import RawData, CalibrationInfo
from .raw_routines import process, save_tes_arrays
from .process_classes import get_analyzed_filename
from ..tools.utils import merge_func

# Need to do caching of open dataset
# Just re-do drift_correct when new data comes in?
# Just re-do calibration when new calibration data comes in?
# Need to save data
# Only works when cal and data are in same file


class AnalysisLoader:
    def __init__(self):
        self.off_filename = None
        self.rd = None
        self.ci = None

    def getAnalysisObjects(self, run, cal=None):
        off_filename = get_filename(run)
        state = get_tes_state(run)
        savefile = get_analyzed_filename(run)
        if self.rd is None:
            self.rd = RawData(off_filename, state, savefile)
            self.off_filename = off_filename
        elif off_filename != self.off_filename:
            self.rd = RawData(off_filename, state, savefile)
            self.off_filename = off_filename
        else:
            self.rd.update(state, savefile)
        if cal is None:
            if run.start.get("scantype", None) == "calibration":
                cal = run
            else:
                cal = get_cal(run)
        cal_savedir = get_save_directory(cal)
        cal_state = get_tes_state(cal)
        line_names = get_line_names(cal)
        cal_filename = get_filename(cal)
        cal_savefile = get_analyzed_filename(cal)

        if self.ci is None:
            self.ci = CalibrationInfo(
                cal_filename,
                cal_state,
                cal_savefile,
                cal_savedir,
                line_names,
                data=self.rd.data,
            )
            self.cal_filename = cal_filename
        elif cal_filename != self.cal_filename:
            self.ci = CalibrationInfo(
                cal_filename,
                cal_state,
                cal_savefile,
                cal_savedir,
                line_names,
                data=self.rd.data,
            )
            self.cal_filename = cal_filename
        else:
            self.ci.update(cal_state, cal_savefile, cal_savedir, line_names)
        return self.rd, self.ci


def process_run(run, loader=None, cal=None, redo=False, overwrite=False, **kwargs):
    """
    Process a single run of data.

    Parameters
    ----------
    run : object
        The run to be processed.
    loader : AnalysisLoader, optional
        An instance of the AnalysisLoader class to be used for loading the data.
        If None, a new AnalysisLoader instance will be created. Default is None.
    cal : object, optional
        The calibration data to be used for the run. If None, the calibration data
        will be obtained from the run itself if it's a calibration run, or from
        the associated calibration run otherwise. Default is None.
    redo : bool, optional
        If True, the run will be processed even if it has already been processed before.
        Default is False.
    overwrite : bool, optional
        If True, the processed data will be saved even if a file with the same name
        already exists. Default is False.
    **kwargs
        Additional keyword arguments to be passed to the processing function.

    Returns
    -------
    None

    """
    if loader is None:
        loader = AnalysisLoader()
    rd, calinfo = loader.getAnalysisObjects(run, cal)
    print(f"Processing {rd.off_filename}, state: {rd.state}")
    process(rd, calinfo, redo=redo, overwrite=overwrite, **kwargs)
    print(f"Saving TES Arrays to {rd.savefile}")
    save_tes_arrays(rd, overwrite=overwrite)


@merge_func(process_run, ["loader", "cal"])
def process_catalog(catalog, skip_bad_ADR=True, parent_catalog=None, **kwargs):
    """
    Process a catalog of runs.

    Parameters
    ----------
    catalog : object
        The catalog to be processed.
    skip_bad_ADR : bool, optional
        If True, runs with bad ADR values will be skipped. Default is True.
    parent_catalog : object, optional
        The parent catalog of the catalog to be processed. If None, the catalog itself will be used. Default is None.
    **kwargs
        Additional keyword arguments to be passed to the processing function.

    Returns
    -------
    None

    """
    loader = AnalysisLoader()
    noise_catalogs = catalog.get_subcatalogs(True, False, False, False)
    for ncat in noise_catalogs:
        scans = ncat.list_meta_key_vals("scan_id")
        smin = min(scans)
        smax = max(scans)
        print(f"Processing from {smin} to {smax}")
        cal_ids = ncat.list_meta_key_vals("last_cal")
        default_cal = list(cal_ids)[0]
        for run in ncat.values():
            if skip_bad_ADR:
                try:
                    last_adr_value = run.baseline["data"]["adr_heater"][1]
                except KeyError:
                    print(
                        f"run {run.start['scan_id']} has no ADR data in baseline, but ADR check was requested, aborting"
                    )
                    raise
                if last_adr_value < 0.1:
                    print(
                        f"Last ADR magnet value for run {run.start['scan_id']} was {last_adr_value}, skipping"
                    )
                    continue
            if parent_catalog is not None:
                cal = parent_catalog[get_cal_id(run, default_cal)]
            else:
                cal = catalog[get_cal_id(run, default_cal)]
            process_run(run, loader, cal, **kwargs)
