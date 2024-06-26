# import mass
import os
import numpy as np
import yaml

from .calibration import summarize_calibration, make_calibration, load_calibration


# Understand how to intelligently re-drift-correct as data comes in
def _drift_correct(data):
    data.learnDriftCorrection()


def drift_correct(rd):
    """
    rd : A RawData object
    """
    if not rd.driftCorrected:
        print("Drift Correcting")
        _drift_correct(rd.data)
        rd.load_ds()
    else:
        print("Drift Correction already done")


# Need to determine when to re-calibrate
def calibrate(rd, calinfo, redo=False, overwrite=False, rms_cutoff=2, **kwargs):
    """
    rd : A RawData object
    calinfo : a CalibrationInfo object
    redo : Whether we should re-calibrate even if calibration is loaded
    overwrite : If we should ignore already on-disk calibration,
                passed to make_calibration, summarize_calibration, and save_tes_arrays
    """
    if not calinfo.calibrated or redo:
        print(f"Calibrating {calinfo.state}")
        make_calibration(calinfo, overwrite=overwrite, rms_cutoff=rms_cutoff, **kwargs)
        summarize_calibration(calinfo, overwrite=overwrite)
        save_tes_arrays(calinfo, overwrite=overwrite)
    else:
        print("Calibration already present")
    if not rd.calibrated:
        print(f"Loading calibration for {rd.state}")
        load_calibration(rd, calinfo)
    else:
        print("Calibration already loaded")


def process(
    rd, calinfo, redo=False, rms_cutoff=0.2, dc=True, overwrite=False, **cal_kwargs
):
    savefile = rd.savefile
    metafile = os.path.splitext(rd.savefile)[0] + ".yaml"
    state = rd.state
    savedir = os.path.dirname(savefile)
    if not os.path.exists(savedir):
        os.makedirs(savedir)
    if os.path.exists(savefile) and not overwrite:
        print(f"Not going to overwrite {savefile}, moving on")
        return

    if dc:
        drift_correct(rd)
        drift_correct(calinfo)
    calibrate(
        rd, calinfo, redo=redo, rms_cutoff=rms_cutoff, overwrite=overwrite, **cal_kwargs
    )


def save_tes_arrays(rd, overwrite=False):
    savefile = rd.savefile
    metafile = os.path.splitext(rd.savefile)[0] + ".yaml"
    state = rd.state
    savedir = os.path.dirname(savefile)
    if not os.path.exists(savedir):
        os.makedirs(savedir)
    if os.path.exists(savefile) and not overwrite:
        print(f"Not overwriting {savefile}")
        return

    timestamps = []
    energies = []
    channels = []
    for ds in rd.data.values():
        try:
            uns, es = ds.getAttr(["unixnano", "energy"], state)
        except:
            print(f"{ds.channum} failed")
            ds.markBad("Failed to get energy")
            continue
        ch = np.zeros_like(uns) + ds.channum
        timestamps.append(uns)
        energies.append(es)
        channels.append(ch)
    ts_arr = np.concatenate(timestamps)
    en_arr = np.concatenate(energies)
    ch_arr = np.concatenate(channels)
    sort_idx = np.argsort(ts_arr)
    print(f"Saving {savefile}")
    np.savez(
        savefile,
        timestamps=ts_arr[sort_idx],
        energies=en_arr[sort_idx],
        channels=ch_arr[sort_idx],
    )
    md = rd.getProcessMd()
    with open(metafile, "w") as f:
        yaml.dump(md, f)
