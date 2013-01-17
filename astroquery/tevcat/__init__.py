# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Get TeVCat table.

TeVCat is a TeV gamma-ray source catalog that is continually updated.

The data can be browsed on the html pages at http://tevcat.uchicago.edu/
but currently there is no download link for the catalog in CSV or FITS format.

However all data on the website is contained in a JSON object
which is easy to extract and process from Python.
This is what we do here, we implement the ``get_tevcat`` function
which converts the JSON data to an `~astropy.table.Table` object
and nicely formats it so that columns have correct data types,
units and descriptions.
We use float columns even for integer values, because that
makes ``NaN`` for missing values available ... string columns use
the empty string ``""`` for missing values.
"""
import json
import re
import urllib2
import base64
import warnings
import numpy as np
from astropy.logger import log
from astropy.table import Table, Column, MaskedColumn
from astropy.coordinates import Angle, IllegalSecondWarning
from astropy import cosmology

__all__ = ['get_tevcat']


def get_tevcat(with_notes=False):
    """Get TeVCat catalog as a table.

    Parameters
    ----------
    with_notes : bool
        Add the ``notes`` column.

    Returns
    -------
    table : `~astropy.table.Table`
        TeVCat catalog table

    Examples
    --------
    >>> from astroquery.tevcat import get_tevcat
    >>> table = get_tevcat()
    """
    tevcat = _TeVCat()

    tevcat._download_data()
    tevcat._extract_version()
    tevcat._extract_data()
    tevcat._make_table(with_notes=with_notes)

    return tevcat.table


class _TeVCat(object):
    """TeVCat info ( http://tevcat.uchicago.edu/ )"""
    URL = 'http://tevcat.uchicago.edu/'

    def _download_data(self):
        """Gets the data and sets the 'data' and 'version' attributes"""
        log.info('Downloading {} (should be ~ 0.5 MB)'.format(self.URL))
        response = urllib2.urlopen(self.URL)
        self._html = response.read()

    def _extract_version(self):
        """"Extract the version number from the html"""
        pattern = 'Current Catalog Version:\s*(.*)\s*'
        matches = re.search(pattern, self._html)
        self.version = matches.group(1)

    def _extract_data(self):
        """Extract the data dict from the html"""
        pattern = 'var jsonData = atob\("(.*)"\);'
        matches = re.search(pattern, self._html)
        encoded_data = matches.group(1)
        decoded_data = base64.decodestring(encoded_data)
        data = json.loads(decoded_data)
        # Keep the full data for debugging
        self._data = data
        # Store the useful parts
        self._sources = data['sources']
        self._catalogs = data['catalogs']

    def _make_table(self, with_notes=False):
        """Convert the data into a table object"""

        # This is the table that will contain the TeVCat
        table = Table()
        table.meta['name'] = 'TeVCat'
        table.meta['version'] = self.version

        # This is a temp table that has mostly columns of type "object"
        # We just use this here as a convenient way to group the column data
        # in arrays (`self._sources` is in a list of dicts format)
        t = Table(self._sources)

        # Fix up column dtype, missing values and unit one by one
        # (alphabetical order).
        table['canonical_name'] = _fix_data(t['canonical_name'])

        table['catalog_id'] = _fix_data(t['catalog_id'], int)

        catalog_id_name = [self._catalogs[str(int(_))]['name']
                           for _ in table['catalog_id']]
        table['catalog_id_name'] = Column(catalog_id_name,
                                          description='Name of sub-catalog containing this source')

        table['catalog_name'] = _fix_data(t['catalog_name'])

        with warnings.catch_warnings(IllegalSecondWarning):
            coord_dec = Angle(t['coord_dec'], 'degree').degree
            table['coord_dec'] = Column(coord_dec, unit='degree',
                                        description='Declination')

            coord_gal_lat = Angle(t['coord_gal_lat'], 'degree').degree
            table['coord_gal_lat'] = Column(coord_gal_lat, unit='degree',
                                            description='Galactic latitude')

            coord_gal_lon = Angle(t['coord_gal_lon'], 'degree').degree
            table['coord_gal_lon'] = Column(coord_gal_lon, unit='degree',
                                            description='Galactic longitude')

            coord_ra = Angle(t['coord_ra'], 'hour').degree
            table['coord_ra'] = Column(coord_ra, unit='degree',
                                       description='Right Ascension')

        # TODO: what does `coord_type` mean?
        coord_type = _fix_data(t['coord_type'], int)
        table['coord_type'] = Column(coord_type, description='Coordinate type')

        # TODO: translate integer code to string
        table['discoverer'] = _fix_data(t['discoverer'], int)

        # Store date in format that can be passed to astropy.time.Time as
        # Time(date, scale='utc', format='iso')
        date = _fix_date(t['discovery_date'])
        table['discovery_date'] = Column(date, description='Discovery date')

        distance = _fix_distance(t)
        table['distance'] = Column(distance, unit='kpc',
                                   description='Distance to source')

        eth = _fix_data(t['eth'], float)
        table['eth'] = Column(eth, unit='TeV', description='Energy threshold')

        # TODO: Which crab flux should be used as reference?
        flux = _fix_data(t['flux'], float)
        table['flux'] = Column(flux, unit='Crab', description='Source flux')

        greens_cat = _fix_data(t['greens_cat'])
        table['greens_cat'] = Column(greens_cat,
                                     description="URL to Green's catalog entry")

        table['id'] = _fix_data(t['id'], int)

        # Omitting `image` column ... not useful.
        # Omitting `marker_id` column ... not useful.

        if with_notes:
            table['notes'] = _fix_data(t['notes'])

        table['observatory_name'] = _fix_data(t['observatory_name'])

        table['other_names'] = _fix_data(t['other_names'])

        table['owner'] = _fix_data(t['owner'], int)

        if with_notes:
            table['private_notes'] = _fix_data(t['private_notes'])

        # Omitting `public` column ... not useful.

        size_x = _fix_data(t['size_x'], float)
        table['size_x'] = Column(size_x, unit='deg',
                                 description='Size (major axis)')

        size_y = _fix_data(t['size_y'], float)
        table['size_y'] = Column(size_y, unit='deg',
                                 description='Size (minor axis)')

        table['source_type'] = _fix_data(t['source_type'], int)

        table['source_type_name'] = _fix_data(t['source_type_name'])

        spec_idx = _fix_data(t['spec_idx'], float)
        table['spec_idx'] = Column(spec_idx, description='Spectral index')

        table['src_rank'] = _fix_data(t['src_rank'], int)

        table['variability'] = _fix_data(t['variability'], int)

        # Store tables (the `sources_table` is mainly useful for debugging)
        self._sources_table = t
        self.table = table


def _fix_data(in_data, dtype=str, fill_value=None):

    # We use float for int columns to make `NaN` available for missing values
    if dtype == int:
        dtype = float

    if fill_value == None:
        if dtype == str:
            fill_value = ''
        elif dtype == float:
            fill_value = np.NAN
        elif dtype == int:
            fill_value = -99

    out_data = []
    for element in in_data:
        if element == None:
            out_data.append(fill_value)
        else:
            if dtype == str:
                element = element.encode('utf8')
            out_data.append(element)
    return np.array(out_data, dtype=dtype)
    # mask = [_ == None for _ in column]
    # return MaskedColumn(data=data, name=column.name, mask)


def _fix_date(in_data):
    out_data = []
    for element in in_data:
        out_data.append(element[0:4] + '-' + element[4:6] + '-01')

    return out_data


def _fix_distance(t):
    distance = _fix_data(t['distance'], float)
    distance_mod = _fix_data(t['distance_mod'], str)
    mask = (distance_mod == 'z')

    try:
        cosmo = cosmology.default_cosmology.get()
    except:
        # compatibility with pre Astropy 0.4
        cosmo = cosmology.get_current()

    distance[mask] = cosmo.luminosity_distance(distance[mask]).to('kpc').value

    return distance