from .run import summarize_run
from ..tes.loader import process_catalog
from ..tes.process_classes import is_run_processed
from .export import export_run_to_analysis_catalog
from databroker.queries import PartialUID, TimeRange, Key
from ..tools.catalog import WrappedCatalogBase
from ..tools.utils import merge_func
import datetime
from tiled.client import from_profile


def getWDB(profile):
    db = from_profile(profile)
    keyMap = {
        "samples": "sample_name",
        "groups": "group_name",
        "edges": "edge",
        "noise": "last_noise",
        "scantype": "scantype",
        "proposal": "proposal",
        "uid": "uid",
        "beamtime_start": "beamtime_start",
    }
    Wrapper = WrapperFactory(keyMap)
    return Wrapper(db)


def getOldWDB(profile):
    db = from_profile(profile)
    keyMap = {
        "samples": "sample_args.sample_name.value",
        "groups": "group_md.name",
        "edges": "edge",
        "noise": "last_noise",
        "scantype": "scantype",
        "proposal": "proposal",
        "uid": "uid",
        "beamtime_start": "beamtime_start",
    }
    Wrapper = WrapperFactory(keyMap)
    return Wrapper(db)


class WrappedDatabroker(WrappedCatalogBase):
    KEY_MAP = {
        "samples": "sample_name",
        "groups": "group_name",
        "edges": "edge",
        "noise": "last_noise",
        "scantype": "scantype",
        "proposal": "proposal",
        "uid": "uid",
        "beamtime_start": "beamtime_start",
    }

    def __init__(self, catalog, parent=None, prefilter=False):
        super().__init__(catalog, parent)
        if prefilter:
            self._catalog = self._filter_by_stop()

    def get_subcatalogs(
        self, noise=True, groups=True, samples=True, edges=True, **kwargs
    ):
        return self._get_subcatalogs(
            noise=noise, groups=groups, samples=samples, edges=edges, **kwargs
        )

    def _filter_by_stop(self):
        ok_uuids = []
        for uid, run in self._catalog.items():
            try:
                if run.metadata["stop"]["exit_status"] == "success":
                    ok_uuids.append(uid)
            except:
                pass
        return self._catalog.search(PartialUID(*ok_uuids))

    def filter_by_time(self, since=None, until=None):
        """
        Return a new catalog filtered to include only scans between the specified times.

        Parameters
        ----------
        since : str, optional
            The start time for the filter, formatted as "YYYY-MM-DD". If not provided, no lower time bound is applied.
        until : str, optional
            The end time for the filter, formatted as "YYYY-MM-DD". If not provided, no upper time bound is applied.

        Returns
        -------
        WrappedDatabroker
            A new instance of the catalog filtered by the specified time range.
        """
        return self.search(TimeRange(since=since, until=until))

    def filter_by_stop(self):
        """
        Filters the catalog to only include scans where the exit status was 'success'.

        Returns
        -------
        WrappedDatabroker
            A new instance of the catalog, filtered to only include successful scans.
        """
        catalog = self._filter_by_stop()
        return self.__class__(catalog, self._parent)

    def filter_by_scanid(self, start, end):
        """
        Filters the catalog to only include scans within a specified range of scan IDs.

        Parameters
        ----------
        start : int
            The starting scan ID of the range.
        end : int
            The ending scan ID of the range.

        Returns
        -------
        WrappedDatabroker
            A new instance of the catalog filtered by the specified scan ID range.
        """
        return self.search(Key("scan_id") >= start).search(Key("scan_id") <= end)

    def get_beamtime(self, since, until=None):
        """
        Get a sub-catalog that has all runs associated with beamtimes that have start dates inside the given start and until times.

        Parameters
        ----------
        since : str
            ISO formatted date string indicating the start time.
        until : str, optional
            ISO formatted date string indicating the end time. If not provided, it defaults to one day after the start time.

        Returns
        -------
        WrappedDatabroker
            A sub-catalog containing all runs associated with beamtimes that have start dates within the specified time range.
        """
        if until is None:
            startdate = datetime.datetime.fromisoformat(since)
            defaultdelta = datetime.timedelta(days=1)
            untildatetime = startdate + defaultdelta
            until = untildatetime.isoformat()
        beamtime_start_vals = (
            self.search(Key("beamtime_start") > since)
            .search(Key("beamtime_start") < until)
            .list_meta_key_vals("beamtime_start")
        )
        return self.filter_by_key("beamtime_start", beamtime_start_vals)

    def list_meta_key_vals(self, key):
        keys = key.split(".")
        vals = set()
        for h in self._catalog.values():
            s = h.metadata["start"]
            for k in keys:
                s = s.get(k, None)
                if s is None:
                    break
            if s is not None:
                vals.add(s)
        return vals

    def filter(self, stop=False, samples=None, groups=None, scantype=None, edges=None):
        if stop:
            catalog = self.filter_by_stop()
            return catalog.filter(
                stop=False,
                samples=samples,
                groups=groups,
                scantype=scantype,
                edges=edges,
            )
        else:
            return super().filter(
                samples=samples, groups=groups, scantype=scantype, edges=edges
            )

    def get_noise_catalogs(self):
        return self._get_subcatalogs(noise=True)

    def describe(self):
        """
        Prints a summary of the catalog, including the number of runs, time range, groups, samples, and scan ID range.

        This method provides a high-level overview of the catalog's contents, highlighting the time range of the data,
        the groups and samples included, and the range of scan IDs.
        """
        nruns = len(self._catalog)
        samples = self.list_samples()
        groups = self.list_groups()
        times = self.list_meta_key_vals("time")
        scans = self.list_meta_key_vals("scan_id")
        start = datetime.datetime.fromtimestamp(min(times)).isoformat()
        stop = datetime.datetime.fromtimestamp(max(times)).isoformat()
        scan_start = min(scans)
        scan_stop = max(scans)
        print(f"Catalog contains {nruns} runs")
        print(f"Time range: {start} to {stop}")
        print(f"Scan ID range: {scan_start} to {scan_stop}")
        print(f"Contains groups {groups}")
        print(f"Contains samples {samples}")

    def summarize(self):
        noise_catalogs = self.get_subcatalogs(True, False, False, False)
        try:
            noise_catalogs.sort(key=lambda c: c[0].start["time"])
        except:
            pass
        for c in noise_catalogs:
            print("Noise Catalog...")
            ntimes = c.list_meta_key_vals("time")
            nstart = datetime.datetime.fromtimestamp(min(ntimes)).isoformat()
            nstop = datetime.datetime.fromtimestamp(max(ntimes)).isoformat()
            scans = c.list_meta_key_vals("scan_id")
            sstart = min(scans)
            sstop = max(scans)

            print(f"Scans {sstart} to {sstop} taken From {nstart} to {nstop}")
            group_catalogs = c.get_subcatalogs(False, True, False, False)
            for g in group_catalogs:
                group = list(g.list_groups())[0]
                print(f"Group {group}:")
                gtimes = g.list_meta_key_vals("time")
                gstart = datetime.datetime.fromtimestamp(min(gtimes)).isoformat()
                gstop = datetime.datetime.fromtimestamp(max(gtimes)).isoformat()
                print(f"From {gstart} to {gstop}")
                samples = g.list_samples()
                print(f"Contains samples {samples}")
                edges = g.list_edges()
                print(f"measured at {edges} edge")

    def list_all_runs(self):
        groupname = ""
        for uid, run in self._catalog.items():
            group = run.metadata["start"].get("group", "")
            if group != groupname:
                groupname = group
                if groupname != "":
                    print(f"Group: {groupname}")
            print("-------------")
            print(f"uid: {uid[:9]}...")
            summarize_run(run)

    @merge_func(export_run_to_analysis_catalog)
    def export_to_analysis(self, skip_unprocessed=True, **kwargs):
        """
        Export the runs in the catalog to the analysis catalog.

        Parameters
        ----------
        skip_unprocessed : bool, optional
            If True, unprocessed runs will be skipped. Default is True.
        """
        for _, run in self._catalog.items():
            if skip_unprocessed:
                if not is_run_processed(run):
                    print(
                        f"Skipping unprocessed run {run.metadata['start']['scan_id']}"
                    )
                    continue
            print(f"Exporting run {run.metadata['start']['scan_id']}")
            export_run_to_analysis_catalog(run, **kwargs)

    @merge_func(process_catalog, ["parent_catalog"])
    def process_tes(self, **kwargs):
        """
        Process the TES data in the catalog.

        Parameters
        ----------
        **kwargs
            Additional keyword arguments to be passed to the processing function.
        """
        process_catalog(self, parent_catalog=self._parent, **kwargs)

    def check_processed(self):
        for uid, run in self._catalog.items():
            print(f"uid: {uid[:9]}...")
            print(f"TES processed: {is_run_processed(run)}")


def WrapperFactory(keyMap):
    class CustomWrapper(WrappedDatabroker):
        KEY_MAP = keyMap

    return CustomWrapper
