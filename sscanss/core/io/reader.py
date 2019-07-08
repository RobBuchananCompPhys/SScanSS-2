"""
A collection of functions for reading data
"""
import re
import os
from collections import OrderedDict
import h5py
import numpy as np
from ..geometry.mesh import Mesh
from ..math.matrix import Matrix44


def read_project_hdf(filename):
    """Reads the project data dictionary from a hdf file

    :param filename: path of the hdf file
    :type filename: str
    :return: A dictionary containing the project data
    :rtype: Dict
    :raises: ValueError
    """
    data = {}
    with h5py.File(filename, 'r') as hdf_file:

        data['name'] = hdf_file.attrs['name']
        data['instrument'] = hdf_file.attrs['instrument_name']

        sample_group = hdf_file['sample']
        sample = OrderedDict()
        for key in sample_group.keys():
            vertices = np.array(sample_group[key]['vertices'])
            normals = np.array(sample_group[key]['normals'])
            indices = np.array(sample_group[key]['indices'])

            sample[key] = Mesh(vertices, indices, normals)

        data['sample'] = sample

        fiducial_group = hdf_file['fiducials']
        points = np.array(fiducial_group['points'])
        enabled = np.array(fiducial_group['enabled'])
        data['fiducials'] = (points, enabled)

        measurement_group = hdf_file['measurement_points']
        points = np.array(measurement_group['points'])
        enabled = np.array(measurement_group['enabled'])
        data['measurement_points'] = (points, enabled)

        data['measurement_vectors'] = np.array(hdf_file['measurement_vectors'])
        if data['measurement_vectors'].shape[0] != data['measurement_points'][0].shape[0]:
            raise ValueError('The number of vectors are not equal to number of points')

        alignment = hdf_file.get('alignment')
        data['alignment'] = alignment if alignment is None else Matrix44(alignment)

    return data


def read_3d_model(filename):
    """Reads a 3D triangular mesh in Obj or STL formats

    :param filename: path of the stl file
    :type filename: str
    :return: The vertices, normals and index array of the mesh
    :rtype: Mesh
    :raises: ValueError
    """
    ext = os.path.splitext(filename)[1].replace('.', '').lower()
    if ext == 'stl':
        mesh = read_stl(filename)
    elif ext == 'obj':
        mesh = read_obj(filename)
    else:
        raise ValueError('"{}" 3D files are currently unsupported.'.format(ext))

    return mesh


def read_stl(filename):
    """Reads a 3D triangular mesh from an STL file. STL has a binary
    and ASCII format and this function attempts to read the file irrespective
    of its format.

    :param filename: path of the stl file
    :type filename: str
    :return: The vertices, normals and index array of the mesh
    :rtype: Mesh
    """
    try:
        return read_ascii_stl(filename)
    except (UnicodeDecodeError, ValueError):
        return read_binary_stl(filename)


def read_ascii_stl(filename):
    """Reads a 3D triangular mesh from an STL file (ASCII format).
    This function is much slower than the binary version due to
    the string split but will have to do for now.

    :param filename: path of the stl file
    :type filename: str
    :return: The vertices, normals and index array of the mesh
    :rtype: Mesh
    :raises: ValueError
    """
    #
    with open(filename, encoding='utf-8') as stl_file:
        offset = 21

        stl_file.readline()
        text = stl_file.read()
        text = text.lower().rsplit('endsolid', 1)[0]
        text = np.array(text.split())
        text_size = len(text)

        if text_size == 0 or text_size % offset != 0:
            raise ValueError('stl data has incorrect size')

        face_count = int(text_size / offset)
        text = text.reshape(-1, offset)
        data_pos = [2, 3, 4, 8, 9, 10, 12, 13, 14, 16, 17, 18]
        normals = text[:, data_pos[0:3]].astype(np.float32)
        vertices = text[:, data_pos[3:]].astype(np.float32)

        vertices = vertices.reshape(-1, 3)
        indices = np.arange(face_count * 3)
        normals = np.repeat(normals, 3, axis=0)

        return Mesh(vertices, indices, normals)


def read_binary_stl(filename):
    """Reads a 3D triangular mesh from an STL file (binary format).

    :param filename: path of the stl file
    :type filename: str
    :return: The vertices, normals and index array of the mesh
    :rtype: Mesh
    :raises: ValueError
    """
    with open(filename, 'rb') as stl_file:
        stl_file.seek(80)
        face_count = np.frombuffer(stl_file.read(4), dtype=np.int32)[0]

        record_dtype = np.dtype([
            ('normals', np.float32, (3,)),
            ('vertices', np.float32, (3, 3)),
            ('attr', '<i2', (1,)),
        ])
        data = np.fromfile(stl_file, dtype=record_dtype)

    if face_count != data.size:
        raise ValueError('stl data has incorrect size')

    vertices = data['vertices'].reshape(-1, 3)
    indices = np.arange(face_count * 3)
    normals = np.repeat(data['normals'], 3, axis=0)

    return Mesh(vertices, indices, normals)


def read_obj(filename):
    """Reads a 3D triangular mesh from an obj file.
    The obj format supports several geometric objects but
    this function reads the face index and vertices only and
    the vertex normals are computed by the Mesh object.

    :param filename: path of the obj file
    :type filename: str
    :return: The vertices, normals and index array of the mesh
    :rtype: Mesh
    """
    vertices = []
    faces = []
    with open(filename, encoding='utf-8') as obj_file:
        for line in obj_file:
            prefix = line[0:2].lower()
            if prefix == 'v ':
                vertices.append(line[1:].split())
            elif prefix == 'f ':
                temp = [val.split('/')[0] for val in line[1:].split()]
                faces.extend(temp[0:3])

    vertices = np.array(vertices, dtype=np.float32)[:, 0:3]

    face_index = np.array(faces, dtype=int) - 1
    vertices = vertices[face_index, :]
    indices = np.arange(face_index.size)

    return Mesh(vertices, indices)


def read_csv(filename):
    """Reads data from a space or comma delimited file.

    :param filename: path of the file
    :type filename: str
    :return: data from file
    :rtype: List[List[str]]
    """
    data = []
    regex = re.compile(r'(\s+|(\s*,\s*))')
    with open(filename) as csv_file:
        for line in csv_file:
            line = regex.sub(' ', line)
            row = line.split()
            if not row:
                continue
            data.append(row)

    return data


def read_points(filename):
    """Reads point data and enabled status from a space or comma delimited file.

    :param filename: path of the file
    :type filename: str
    :return: 3D points and enabled status
    :rtype: Tuple[numpy.ndarray, list[bool]]
    :raises: ValueError
    """
    points = []
    enabled = []
    data = read_csv(filename)
    for row in data:
        if len(row) == 3:
            points.append(row)
            enabled.append(True)
        elif len(row) == 4:
            *p, d = row
            d = False if d.lower() == 'false' else True
            points.append(p)
            enabled.append(d)
        else:
            raise ValueError('data has incorrect size')

    return np.array(points, np.float32), enabled


def read_vectors(filename):
    """Reads measurement vectors from a space or comma delimited file.

    :param filename: path of the file
    :type filename: str
    :return: array of vectors
    :rtype:  numpy.ndarray
    :raises: ValueError
    """
    vectors = []
    data = read_csv(filename)
    expected_size = len(data[0])
    if expected_size % 3 != 0:
        raise ValueError('Column size of vector data must be a multiple of 3.')

    for row in data:
        if len(row) == expected_size:
            vectors.append(row)
        else:
            raise ValueError('Inconsistent column size of vector data.')

    return np.array(vectors, np.float32)


def read_trans_matrix(filename):
    """Reads transformation matrix from a space or comma delimited file.

    :param filename: path of the file
    :type filename: str
    :return: transformation matrix
    :rtype: Matrix44
    :raises: ValueError
    """
    matrix = []
    data = read_csv(filename)
    if len(data) != 4:
        raise ValueError('data has incorrect size')

    for row in data:
        if len(row) == 4:
            matrix.append(row)
        else:
            raise ValueError('data has incorrect size')

    return Matrix44(matrix, np.float32)


def read_fpos(filename):
    """Reads index, points, and positioner pose from a space or comma delimited file.

    :param filename: path of the file
    :type filename: str
    :return: index, points, and positioner pose
    :rtype: Tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]
    :raises: ValueError
    """
    index = []
    points = []
    pose = []
    data = read_csv(filename)
    expected_size = len(data[0])
    if expected_size < 4:
        raise ValueError('data has incorrect size')

    for row in data:
        if len(row) != expected_size:
            raise ValueError('Inconsistent column size of fpos data.')
        index.append(row[0])
        points.append(row[1:4])
        pose.append(row[4:])

    return np.array(index, int) - 1, np.array(points, np.float32), np.array(pose, np.float32)
