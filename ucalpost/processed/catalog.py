"""
A module to deal with fully-processed xastools-like spectra
"""
from ..tools.catalog import WrappedCatalogBase
from tiled.queries import Key
from functools import reduce


class WrappedAnalysis(WrappedCatalogBase):
    KEY_MAP = {"samples": "scaninfo.sample", "groups": "scaninfo.group_md.name",
               "edges": "scaninfo.element", "loadid": "scaninfo.loadid",
               "scans": "scaninfo.scan"}

    def get_subcatalogs(self, groups=True, samples=True, edges=True):
        return self._get_subcatalogs(groups=groups, samples=samples, edges=edges)

    def list_meta_key_vals(self, key):
        keys = key.split('.')
        vals = set()
        for h in self._catalog.values():
            s = h.metadata
            for k in keys:
                s = s.get(k, None)
                if s is None:
                    break
            if s is not None:
                vals.add(s)
        return vals

    def filter(self, samples=None, groups=None, edges=None):
        return super().filter(samples=samples, groups=groups, edges=edges)

    def summarize(self):
        for h in self._catalog.values():
            scaninfo = h.metadata['scaninfo']
            print(f"Date: {scaninfo['date']}")
            print(f"Scan: {scaninfo['scan']}")
            print(f"Group: {scaninfo['group_md']['name']}")
            print(f"Sample: {scaninfo['sample']} Edge: {scaninfo['element']}")

    def describe(self):
        desc_dict = {}
        for h in self._catalog.values():
            scaninfo = h.metadata['scaninfo']
            scan = scaninfo['scan']
            group = scaninfo['group_md']['name']
            sample = scaninfo['sample']
            edge = scaninfo['element']
            if group not in desc_dict:
                desc_dict[group] = {}
            group_dict = desc_dict[group]
            if sample not in group_dict:
                group_dict[sample] = {}
            sample_dict = group_dict[sample]
            if edge not in sample_dict:
                sample_dict[edge] = []
            edge_list = sample_dict[edge]
            edge_list.append(scan)
        for group, group_dict in desc_dict.items():
            print("-------------------------")
            print(f"Group: {group}")
            for sample, sample_dict in group_dict.items():
                print(f"Sample: {sample}")
                for edge, edge_list in sample_dict.items():
                    print(f"Edge: {edge}, Scans: {edge_list}")

    def get_xas(self, subcatalogs=True):
        if subcatalogs:
            catalogs = self.get_subcatalogs()
            xas = [c.get_xas(False) for c in catalogs]
            return xas
        else:
            allxas = [v.to_xas() for v in self._catalog.values()]
            if len(allxas) > 1:
                xas = reduce(lambda x, y: x + y, allxas)
            else:
                xas = allxas[0]
            return xas
