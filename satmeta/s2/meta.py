import re
import functools

from . import metafile
from . import utils as s2utils

from satmeta import converters

_all_res = [10, 20, 60]


def _get_sizes(root):
    """Get image sizes for all available resolutions"""
    sizes = {}
    for res in _all_res:
        sizes[res] = {}
        for dim in ['NROWS', 'NCOLS']:
            sizetag = (
                    './/Size[@resolution=\'{res}\']/{dim}'
                    ''.format(res=res, dim=dim))
            sizes[res][dim] = int(root.findall(sizetag)[0].text)
    return sizes


def _get_geopositions(root):
    """Get geoposition from XML root"""
    geopos = {}
    for res in _all_res:
        geopos[res] = {}
        for corner in ['ULX', 'ULY']:
            sizetag = (
                    './/Geoposition[@resolution=\'{res}\']/{corner}'
                    ''.format(res=res, corner=corner))
            geopos[res][corner] = int(root.findall(sizetag)[0].text)
    return geopos


def generate_image_transform(image_geoposition):
    """Generate image transform (affine.Affine) from image_geoposition dict"""
    image_transform = {}
    for res in image_geoposition:
        image_transform[res] = s2utils.kw_to_affine(
            COL_STEP=res, ROW_STEP=res, **image_geoposition[res])
    return image_transform


def generate_image_shape(image_size):
    image_shape = {}
    for res in image_size:
        image_shape[res] = [
                image_size[res][k] for k in ['NROWS', 'NCOLS']]
    return image_shape


def generate_image_bounds(image_transform, image_shape):
    """left bottom right top"""
    image_bounds = {}
    for res in image_transform:
        image_bounds[res] = converters.trans_shape_to_bounds(
                image_transform[res], image_shape[res])
    return image_bounds


def tile_name_from_tile_ID(tile_ID):
    """Get tile name (TZZAAA) from tile ID or file name"""
    try:
        return re.search('(?<=T)\d{2}[A-Z]{3}', tile_ID).group(0)
    except AttributeError:
        raise ValueError(
                'Unable to get tile name from ID \'{}\'.'.format(tile_ID))


def sensor_ID_from_product_name(product_name):
    try:
        return re.search('^S2[AB]', product_name).group(0)
    except AttributeError:
        raise ValueError(
                'Unable to get sensor ID from product name \'{}\'.'.format(product_name))


def sensor_ID_from_spacecraft_name(spacecraft_name):
    try:
        return 'S' + re.search('^Sentinel-(2[AB])', spacecraft_name).group(1)
    except AttributeError:
        raise ValueError(
                'Unable to get sensor ID from spacecraft name \'{}\'.'.format(spacecraft_name))


def parse_granule_metadata(metadatafile=None, metadatastr=None):
    """Parse S2 GRANULE meta data from file or string"""
    root = converters.get_root(metadatafile, metadatastr)
    return parse_granule_metadata_xml(root)


def parse_metadata(metadatafile=None, metadatastr=None):
    """Parse S2 PRODUCT meta data from file or string"""
    root = converters.get_root(metadatafile, metadatastr)
    return parse_metadata_xml(root)


def parse_granule_metadata_xml(root):
    """Parse S2 GRANULE meta data XML"""
    _get_single = functools.partial(converters.get_single, root)
    metadata = {
            'tile_ID': _get_single('TILE_ID'),
            'sun_senith': _get_single('Mean_Sun_Angle/ZENITH_ANGLE', to_type=float),
            'sun_azimuth': _get_single('Mean_Sun_Angle/AZIMUTH_ANGLE', to_type=float),
            'sensor_senith': converters.get_all(root,
                'Mean_Viewing_Incidence_Angle_List/Mean_Viewing_Incidence_Angle/ZENITH_ANGLE',
                to_type=float),
            'sensor_azimuth': converters.get_all(root,
                'Mean_Viewing_Incidence_Angle_List/Mean_Viewing_Incidence_Angle/AZIMUTH_ANGLE',
                to_type=float),
            'projection': _get_single('HORIZONTAL_CS_CODE'),
            'cloudCoverPercent': _get_single('CLOUDY_PIXEL_PERCENTAGE', to_type=float),
            'image_size': _get_sizes(root),
            'image_geoposition': _get_geopositions(root)}
    metadata['tile_name'] = tile_name_from_tile_ID(metadata['tile_ID'])
    metadata['image_transform'] = generate_image_transform(
            metadata['image_geoposition'])
    metadata['image_shape'] = generate_image_shape(metadata['image_size'])
    metadata['image_bounds'] = generate_image_bounds(
            metadata['image_transform'], metadata['image_shape'])
    return metadata


def parse_metadata_xml(root):
    """Parse S2 PRODUCT meta data XML"""
    _get_single = functools.partial(converters.get_single, root)
    metadata = {
            'productName': _get_single('PRODUCT_URI'),
            'startTime': converters.get_single_date(root, 'PRODUCT_START_TIME'),
            'processing_level': _get_single('PROCESSING_LEVEL'),
            'spacecraft': _get_single('SPACECRAFT_NAME'),
            'orbit_direction': _get_single('SENSING_ORBIT_DIRECTION'),
            'quantification_value': _get_single(
                'QUANTIFICATION_VALUE', to_type=int),
            'reflectance_conversion': _get_single(
                'Reflectance_Conversion/U', to_type=float),
            'irradiance_values': converters.get_all(root,
                'Reflectance_Conversion/Solar_Irradiance_List/SOLAR_IRRADIANCE', to_type=float)}
    metadata['sensor_ID'] = sensor_ID_from_spacecraft_name(metadata['spacecraft'])
    return metadata


def find_parse_metadata(
        infile, check_granules=False, flatten_single_granule=False):
    """Find and parse product and granule meta data in SAFE or zip file

    Parameters
    ----------
    infile : str
        path to input file SAFE or zip
    check_granules : bool
        check whether granules were loaded
    flatten_single_granule : bool
        merge granule metadata into metadata dictionary

    Returns
    -------
    product meta data dictionary with 'granules' key
    """
    if infile.endswith('.SAFE'):
        mstr = metafile.read_metafile_SAFE(infile)
    elif infile.endswith('.zip'):
        mstr = metafile.read_metafile_ZIP(infile)
    else:
        raise ValueError('This function works only for .SAFE or .zip.')
    metadata = parse_metadata(metadatastr=mstr)
    gmeta = find_parse_granule_metadata(infile)
    if check_granules and not gmeta:
        raise ValueError(
                'No granule metadata found in file \'{}\'.'.format(infile))

    if flatten_single_granule:
        if len(gmeta) != 1:
            raise ValueError('Cannot merge granule metadata because there are '
                    'several granules in product: {}'.format(set(gmeta)))
        metadata.update(gmeta)
    else:
        metadata['granules'] = gmeta
    return metadata


def find_parse_granule_metadata(infile):
    """Find and parse granule meta data in SAFE or zip"""
    granulesdict = {}
    if infile.endswith('.SAFE'):
        for mf in metafile.find_granule_metafiles_in_SAFE(infile):
            gmeta = parse_granule_metadata(metadatafile=mf)
            granulesdict[gmeta['tile_name']] = gmeta
    elif infile.endswith('.zip'):
        for mstr in metafile.read_granule_metafiles_ZIP(infile):
            gmeta = parse_granule_metadata(metadatastr=mstr)
            granulesdict[gmeta['tile_name']] = gmeta
    else:
        raise ValueError('This function works only for .SAFE or .zip.')
    return granulesdict
