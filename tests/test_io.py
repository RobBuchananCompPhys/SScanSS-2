import unittest
import unittest.mock as mock
import shutil
import tempfile
import os
import warnings
import h5py
import numpy as np
from sscanss.core.geometry import Mesh, Volume
from sscanss.core.instrument import read_instrument_description_file, Link
from sscanss.core.io import reader, writer, BadDataWarning
from sscanss.core.math import Matrix44
from sscanss.config import __version__
from tests.helpers import SAMPLE_IDF


class TestIO(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

        self.reader_report_mock = self.createMock("sscanss.core.io.reader.ProgressReport")
        self.writer_report_mock = self.createMock("sscanss.core.io.writer.ProgressReport")

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def createMock(self, module, instance=None):
        if instance is None:
            patcher = mock.patch(module, autospec=True)
        else:
            patcher = mock.patch(module, instance)
        self.addCleanup(patcher.stop)
        return patcher.start()

    @mock.patch("sscanss.core.io.writer.settings", autospec=True)
    @mock.patch("sscanss.core.instrument.create.read_visuals", autospec=True)
    def testHDFReadWrite(self, visual_fn, setting_cls):

        visual_fn.return_value = Mesh(
            np.array([[0, 0, 0], [0, 1, 0], [0, 1, 1]]),
            np.array([0, 1, 2]),
            np.array([[1, 0, 0], [1, 0, 0], [1, 0, 0]]),
        )
        filename = self.writeTestFile("instrument.json", SAMPLE_IDF)
        instrument = read_instrument_description_file(filename)
        data = {
            "name": "Test Project",
            "instrument": instrument,
            "instrument_version": "2.0",
            "sample": None,
            "fiducials": np.recarray((0, ), dtype=[("points", "f4", 3), ("enabled", "?")]),
            "measurement_points": np.recarray((0, ), dtype=[("points", "f4", 3), ("enabled", "?")]),
            "measurement_vectors": np.empty((0, 3, 1), dtype=np.float32),
            "alignment": None,
        }

        filename = os.path.join(self.test_dir, "test.h5")

        writer.write_project_hdf(data, filename)
        result, instrument = reader.read_project_hdf(filename)

        self.assertEqual(str(__version__), result["version"])
        self.assertEqual(data["instrument_version"], result["instrument_version"])
        self.assertEqual(data["name"], result["name"], "Save and Load data are not Equal")
        self.assertEqual(data["instrument"].name, result["instrument"], "Save and Load data are not Equal")
        self.assertIsNone(result["sample"])
        self.assertTrue(result["fiducials"][0].size == 0 and result["fiducials"][1].size == 0)
        self.assertTrue(result["measurement_points"][0].size == 0 and result["measurement_points"][1].size == 0)
        self.assertTrue(result["measurement_vectors"].size == 0)
        self.assertIsNone(result["alignment"])
        self.assertEqual(result["settings"], {})

        vertices = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0]])
        normals = np.array([[0, 0, 1], [0, 0, 1], [0, 0, 1]])
        indices = np.array([0, 1, 2])
        mesh_to_write = Mesh(vertices, indices, normals)
        fiducials = np.rec.array(
            [([11.0, 12.0, 13.0], False), ([14.0, 15.0, 16.0], True), ([17.0, 18.0, 19.0], False)],
            dtype=[("points", "f4", 3), ("enabled", "?")],
        )
        points = np.rec.array(
            [([1.0, 2.0, 3.0], True), ([4.0, 5.0, 6.0], False), ([7.0, 8.0, 9.0], True)],
            dtype=[("points", "f4", 3), ("enabled", "?")],
        )
        vectors = np.zeros((3, 3, 2))
        vectors[:, :, 0] = [
            [0.0000076, 1.0000000, 0.0000480],
            [0.0401899, 0.9659270, 0.2556752],
            [0.1506346, 0.2589932, 0.9540607],
        ]

        vectors[:, :, 1] = [
            [0.1553215, -0.0000486, 0.9878640],
            [0.1499936, -0.2588147, 0.9542100],
            [0.0403915, -0.9658791, 0.2558241],
        ]
        base = Matrix44(np.random.random((4, 4)))
        stack_name = "Positioning Table + Huber Circle"
        new_collimator = "Snout 100mm"
        jaw_aperture = [7.0, 5.0]

        data = {
            "name": "demo",
            "instrument": instrument,
            "instrument_version": "1.1",
            "sample": mesh_to_write,
            "fiducials": fiducials,
            "measurement_points": points,
            "measurement_vectors": vectors,
            "alignment": np.identity(4),
        }

        instrument.loadPositioningStack(stack_name)
        instrument.positioning_stack.fkine([200.0, 0.0, 0.0, np.pi, 0.0])
        instrument.positioning_stack.links[0].ignore_limits = True
        instrument.positioning_stack.links[4].locked = True
        aux = instrument.positioning_stack.auxiliary[0]
        instrument.positioning_stack.changeBaseMatrix(aux, base)

        instrument.jaws.aperture = jaw_aperture
        instrument.jaws.positioner.fkine([-600.0])
        instrument.jaws.positioner.links[0].ignore_limits = True
        instrument.jaws.positioner.links[0].locked = True

        instrument.detectors["Detector"].current_collimator = new_collimator
        instrument.detectors["Detector"].positioner.fkine([np.pi / 2, 100.0])
        instrument.detectors["Detector"].positioner.links[0].ignore_limits = True
        instrument.detectors["Detector"].positioner.links[1].locked = True

        setting_cls.local = {"num": 1, "str": "string", "colour": (1, 1, 1, 1)}

        writer.write_project_hdf(data, filename)
        result, instrument2 = reader.read_project_hdf(filename)
        self.assertEqual(str(__version__), result["version"])
        self.assertEqual(data["name"], result["name"], "Save and Load data are not Equal")
        self.assertEqual(data["instrument_version"], result["instrument_version"])
        self.assertEqual(data["instrument"].name, result["instrument"], "Save and Load data are not Equal")
        np.testing.assert_array_almost_equal(fiducials.points, result["fiducials"][0], decimal=5)
        np.testing.assert_array_almost_equal(points.points, result["measurement_points"][0], decimal=5)
        np.testing.assert_array_almost_equal(result["sample"].vertices, vertices, decimal=5)
        np.testing.assert_array_almost_equal(result["sample"].indices, indices, decimal=5)
        np.testing.assert_array_almost_equal(result["sample"].normals, normals, decimal=5)
        np.testing.assert_array_almost_equal(fiducials.points, result["fiducials"][0], decimal=5)
        np.testing.assert_array_almost_equal(points.points, result["measurement_points"][0], decimal=5)
        np.testing.assert_array_equal(fiducials.enabled, result["fiducials"][1])
        np.testing.assert_array_equal(points.enabled, result["measurement_points"][1])
        np.testing.assert_array_almost_equal(vectors, result["measurement_vectors"], decimal=5)
        np.testing.assert_array_almost_equal(result["alignment"], np.identity(4), decimal=5)
        setting = result["settings"]
        self.assertEqual(setting["num"], 1)
        self.assertEqual(setting["str"], "string")
        self.assertEqual(tuple(setting["colour"]), (1, 1, 1, 1))

        self.assertEqual(instrument.positioning_stack.name, instrument2.positioning_stack.name)
        np.testing.assert_array_almost_equal(instrument.positioning_stack.configuration,
                                             instrument2.positioning_stack.configuration,
                                             decimal=5)
        for link1, link2 in zip(instrument.positioning_stack.links, instrument2.positioning_stack.links):
            self.assertEqual(link1.ignore_limits, link2.ignore_limits)
            self.assertEqual(link1.locked, link2.locked)
        for aux1, aux2 in zip(instrument.positioning_stack.auxiliary, instrument2.positioning_stack.auxiliary):
            np.testing.assert_array_almost_equal(aux1.base, aux2.base, decimal=5)

        np.testing.assert_array_almost_equal(instrument.jaws.aperture, instrument2.jaws.aperture, decimal=5)
        np.testing.assert_array_almost_equal(instrument.jaws.aperture_lower_limit,
                                             instrument2.jaws.aperture_lower_limit,
                                             decimal=5)
        np.testing.assert_array_almost_equal(instrument.jaws.aperture_upper_limit,
                                             instrument2.jaws.aperture_upper_limit,
                                             decimal=5)
        np.testing.assert_array_almost_equal(instrument.jaws.positioner.configuration,
                                             instrument2.jaws.positioner.configuration,
                                             decimal=5)
        for link1, link2 in zip(instrument.jaws.positioner.links, instrument2.jaws.positioner.links):
            self.assertEqual(link1.ignore_limits, link2.ignore_limits)
            self.assertEqual(link1.locked, link2.locked)

        detector1 = instrument.detectors["Detector"]
        detector2 = instrument2.detectors["Detector"]
        self.assertEqual(detector1.current_collimator.name, detector2.current_collimator.name)
        np.testing.assert_array_almost_equal(detector1.positioner.configuration,
                                             detector2.positioner.configuration,
                                             decimal=5)
        for link1, link2 in zip(detector1.positioner.links, detector2.positioner.links):
            self.assertEqual(link1.ignore_limits, link2.ignore_limits)
            self.assertEqual(link1.locked, link2.locked)

        volume = Volume(np.full((5, 4, 3), [-1, 0, 1], dtype=np.float32), np.ones(3), np.array([1., 1.5, 2.]))
        data['sample'] = volume
        writer.write_project_hdf(data, filename)
        result, _ = reader.read_project_hdf(filename)
        np.testing.assert_array_almost_equal(result["sample"].data, volume.data, decimal=5)
        np.testing.assert_array_almost_equal(result["sample"].transform_matrix, volume.transform_matrix, decimal=5)
        np.testing.assert_array_almost_equal(result["sample"].voxel_size, volume.voxel_size, decimal=5)

        # Backward compatibility
        volume_mesh = volume.asMesh()
        volume_mesh.computeNormals()
        with h5py.File(filename, 'a') as hdf:
            del hdf['main_sample']
        result, _ = reader.read_project_hdf(filename)
        np.testing.assert_array_almost_equal(result["sample"].vertices, volume_mesh.vertices, decimal=5)
        np.testing.assert_array_almost_equal(result["sample"].normals, volume_mesh.normals, decimal=5)
        np.testing.assert_array_equal(result["sample"].indices, volume_mesh.indices)

        with h5py.File(filename, 'a') as hdf:
            del hdf['sample']['unnamed']['vertices']
            del hdf['sample']['unnamed']['indices']
            hdf['sample']['unnamed']['vertices'] = mesh_to_write.vertices
            hdf['sample']['unnamed']['indices'] = mesh_to_write.indices
            group = hdf['sample'].create_group('unnamed2')
            group['vertices'] = mesh_to_write.vertices + 2
            group['indices'] = mesh_to_write.indices

        result, _ = reader.read_project_hdf(filename)
        vertices = np.row_stack((mesh_to_write.vertices, mesh_to_write.vertices + 2))
        normals = np.row_stack((mesh_to_write.normals, mesh_to_write.normals))
        np.testing.assert_array_almost_equal(result["sample"].vertices, vertices, decimal=5)
        np.testing.assert_array_almost_equal(result["sample"].normals, normals, decimal=5)
        np.testing.assert_array_almost_equal(result["sample"].indices, np.arange(6, dtype=int))

        data["measurement_vectors"] = np.ones((3, 3, 2))  # invalid normals
        writer.write_project_hdf(data, filename)
        self.assertRaises(ValueError, reader.read_project_hdf, filename)

        data["measurement_vectors"] = np.ones((3, 6, 2))  # more vector than detectors
        writer.write_project_hdf(data, filename)
        self.assertRaises(ValueError, reader.read_project_hdf, filename)

        data["measurement_vectors"] = np.ones((4, 3, 2))  # more vectors than points
        writer.write_project_hdf(data, filename)
        self.assertRaises(ValueError, reader.read_project_hdf, filename)

    def testReadTomoprocHdf(self):
        # Write nexus file
        data = np.full((5, 4, 3), [0, 127, 255], np.uint8).transpose()
        nxs_data = {
            'entry/data/data/x': [0, 1, 2],
            'entry/data/data/y': [3, 4, 5, 6],
            'entry/data/data/z': [6, 7, 8, 9, 10],
            'entry/data/data/data': data,
            'entry/data/definition': b'NXtomoproc',
            'entry/definition': b'TOFRAW'
        }
        filename = os.path.join(self.test_dir, "test.h5")
        h = h5py.File(str(filename), 'w')
        for key, value in nxs_data.items():
            h.create_dataset(str(key), data=value)
        h['entry'].attrs['NX_class'] = u'NXentry'
        h.close()

        # Check data read correctly
        with warnings.catch_warnings(record=True) as warning:
            volume_data, voxel_size, centre = reader.read_tomoproc_hdf(filename)
            self.assertEqual(len(warning), 0)
        np.testing.assert_equal(volume_data, data)
        np.testing.assert_array_almost_equal(voxel_size, np.ones(3), decimal=5)
        np.testing.assert_array_almost_equal(centre, [1.0, 4.5, 8.0], decimal=5)

        data2 = np.full((5, 4, 3), [0, 32768, 65535], np.uint16).transpose()
        # Check that error is thrown when arrays don't match
        with h5py.File(filename, 'r+') as h:
            del h['entry/data/data/data']  # Needed as you can't change in place to a different size in h5py
            h['entry/data/data/data'] = data2
        with warnings.catch_warnings(record=True) as warning:
            volume_data, voxel_size, centre = reader.read_tomoproc_hdf(filename)
            self.assertEqual(len(warning), 0)
        np.testing.assert_equal(volume_data, data)
        np.testing.assert_array_almost_equal(voxel_size, np.ones(3), decimal=5)
        np.testing.assert_array_almost_equal(centre, [1.0, 4.5, 8.0], decimal=5)

        data2 = np.full((5, 4, 3), [np.inf, np.nan, -np.inf], np.float32).transpose()
        with h5py.File(filename, 'r+') as h:
            del h['entry/data/data/data']
            h['entry/data/data/data'] = data2
        self.assertRaises(ValueError, reader.read_tomoproc_hdf, filename)

        data2 = np.full((5, 4, 3), [np.nan, 0.5, 1.0], np.float32).transpose()
        # Check that error is thrown when arrays don't match
        with h5py.File(filename, 'r+') as h:
            del h['entry/data/data/data']
            h['entry/data/data/data'] = data2
        with self.assertWarns(BadDataWarning):
            volume_data, voxel_size, centre = reader.read_tomoproc_hdf(filename)
        np.testing.assert_equal(volume_data, np.full((5, 4, 3), [0, 0, 255], np.uint8).transpose())
        np.testing.assert_array_almost_equal(voxel_size, np.ones(3), decimal=5)
        np.testing.assert_array_almost_equal(centre, [1.0, 4.5, 8.0], decimal=5)

        data2 = np.full((5, 4, 3), [-0.5, 0, 0.5], np.float32).transpose()
        # Check that error is thrown when arrays don't match
        with h5py.File(filename, 'r+') as h:
            del h['entry/data/data/data']
            h['entry/data/data/data'] = data2
        with warnings.catch_warnings(record=True) as warning:
            volume_data, voxel_size, centre = reader.read_tomoproc_hdf(filename)
            self.assertEqual(len(warning), 0)
        np.testing.assert_equal(volume_data, data)
        np.testing.assert_array_almost_equal(voxel_size, np.ones(3), decimal=5)
        np.testing.assert_array_almost_equal(centre, [1.0, 4.5, 8.0], decimal=5)

        with mock.patch('sscanss.core.io.reader.psutil.virtual_memory') as mock_psutil:
            # Test for files which are too large to load
            mock_psutil.return_value.available = 1
            self.assertRaises(MemoryError, reader.read_tomoproc_hdf, filename)

        with h5py.File(filename, 'r+') as h:
            del h['entry/data/data/data']  # Needed as you can't change in place to a different size in h5py
            h['entry/data/data/data'] = np.ones((3, 4, 5))
        self.assertRaises(TypeError, reader.read_tomoproc_hdf, filename)

        # Check that error is thrown when arrays don't match
        with h5py.File(filename, 'r+') as h:
            del h['entry/data/data/x']  # Needed as you can't change in place to a different size in h5py
            h['entry/data/data/x'] = [0, 1]
        self.assertRaises(ValueError, reader.read_tomoproc_hdf, filename)
        # Check that error is thrown when no NXtomoproc exists
        with h5py.File(filename, 'r+') as h:
            del h['entry'].attrs['NX_class']
        self.assertRaises(AttributeError, reader.read_tomoproc_hdf, filename)

    def testFileSortKey(self):
        list_of_strings = ['home/test_034', 'home/test_031', 'home/test_033', 'home/test_032']
        sorted_list = sorted(list_of_strings, key=reader.filename_sorting_key)
        self.assertListEqual(sorted_list, ['home/test_031', 'home/test_032', 'home/test_033', 'home/test_034'])

        list_of_strings = ['C:/home/recon001', 'C:/home/recon010', 'C:/home/recon008', 'C:/home/recon004']
        sorted_list = sorted(list_of_strings, key=reader.filename_sorting_key)
        self.assertListEqual(sorted_list,
                             ['C:/home/recon001', 'C:/home/recon004', 'C:/home/recon008', 'C:/home/recon010'])

    @mock.patch('sscanss.core.io.reader.os.listdir', return_value=["test_file.png", "test_file.tiff", "test_file.tif"])
    def testFileWalker(self, _mock_os_listdir):
        filepath = self.test_dir
        correct_name1 = os.path.join(filepath, "test_file.tiff")
        correct_name2 = os.path.join(filepath, "test_file.tif")
        wrong_name1 = os.path.join(filepath, "test_file.png")
        wrong_name2 = os.path.join(filepath, "test_file2.tiff")
        self.assertNotIn(wrong_name1, reader.file_walker(filepath))
        self.assertIn(wrong_name1, reader.file_walker(filepath, extension=(".tiff", ".tif", ".png")))
        self.assertNotIn(wrong_name2, reader.file_walker(filepath))
        self.assertIn(correct_name1, reader.file_walker(filepath))
        self.assertIn(correct_name2, reader.file_walker(filepath))

    def testReadAndWriteVolumeFromTiffs(self):
        with mock.patch('sscanss.core.io.reader.file_walker', return_value=[]):
            # Test empty folder
            self.assertRaises(ValueError, reader.create_volume_from_tiffs, self.test_dir)

        data = np.ones((3, 3, 3))
        volume = Volume(np.ones((3, 3, 3)), np.ones(3), np.zeros(3), np.histogram(data))
        self.assertEqual(len(os.listdir(self.test_dir)), 0)
        writer.write_volume_as_images(self.test_dir, volume)
        self.assertEqual(len(os.listdir(self.test_dir)), 3)
        self.assertRaises(TypeError, reader.create_volume_from_tiffs, self.test_dir)

        volume.data = np.full((3, 3, 3), np.nan, dtype=np.float32)
        writer.write_volume_as_images(self.test_dir, volume)
        self.assertRaises(ValueError, reader.create_volume_from_tiffs, self.test_dir)

        expected_data = np.full((3, 3, 3), [0, 127, 255], np.uint8)
        size = np.ones(3)
        centre = np.zeros(3)
        volume = Volume(expected_data, size, centre, np.histogram(expected_data))
        writer.write_volume_as_images(self.test_dir, volume)
        new_volume_data = reader.create_volume_from_tiffs(self.test_dir)
        self.assertEqual(new_volume_data.dtype, np.uint8)
        np.testing.assert_array_equal(new_volume_data, expected_data)

        expected_data = np.full((3, 3, 3), [0, 127, 255], np.uint8)
        data = np.full((3, 3, 3), [0, 32768, 65535], np.uint16)
        volume = Volume(data, size, centre, np.histogram(data))
        writer.write_volume_as_images(self.test_dir, volume)
        new_volume_data = reader.create_volume_from_tiffs(self.test_dir)
        self.assertEqual(new_volume_data.dtype, np.uint8)
        np.testing.assert_array_equal(new_volume_data, expected_data)

        with warnings.catch_warnings(record=True) as warning:
            data = np.full((3, 3, 3), [-0.5, 0., 0.5], np.float32)
            volume = Volume(data, size, centre, np.histogram(data))
            writer.write_volume_as_images(self.test_dir, volume)
            self.assertEqual(len(os.listdir(self.test_dir)), 3)
            new_volume_data = reader.create_volume_from_tiffs(self.test_dir)
            self.assertEqual(new_volume_data.dtype, np.uint8)
            np.testing.assert_array_equal(new_volume_data, expected_data)
            self.assertEqual(len(warning), 0)

        expected_data = np.ones((2, 2, 3), dtype=np.uint8) * 255
        expected_data[0, 0, 0] = 0
        expected_data[:, :, 2] = 0
        volume.data = (expected_data / 255).astype(np.float32)
        volume.data[0, 0, 0] = np.nan
        volume.data[0, 0, 2] = -np.inf
        writer.write_volume_as_images(self.test_dir, volume)
        for i in range(3):
            old = os.path.join(self.test_dir, f'{i + 1}.tiff')
            new_path = os.path.join(self.test_dir, f'test_file{i + 1}.tiff')
            os.rename(old, new_path)

        # Test .tiff and non symmetric dataset
        # with self.assertWarns(BadDataWarning):
        #     volume = reader.create_volume_from_tiffs(self.test_dir)
        # np.testing.assert_array_almost_equal(volume.voxel_size, [2, 1, 0.5], decimal=5)
        # np.testing.assert_array_almost_equal(volume.transform_matrix[:3, 3], [-1.5, 0., 1.5], decimal=5)
        # np.testing.assert_array_equal(volume.data, expected_data)

        for i in range(3):
            old = os.path.join(self.test_dir, f'test_file{i + 1}.tiff')
            os.rename(old, old[:-1])  # change extension from tiff to tif

        # Test .tif and different voxel size
        # with self.assertWarns(BadDataWarning):
        #     volume = reader.create_volume_from_tiffs(self.test_dir, [2., 2., 2.], [0., 0., 0.])
        # np.testing.assert_array_almost_equal(volume.voxel_size, [2., 2., 2.], decimal=5)
        # np.testing.assert_array_almost_equal(volume.transform_matrix[:3, 3], [0., 0., 0.], decimal=5)
        # np.testing.assert_array_equal(volume.data, expected_data)

        with mock.patch('sscanss.core.io.reader.psutil.virtual_memory') as mock_psutil:
            # Test for files which are too large to load
            mock_psutil.return_value.available = 1
            self.assertRaises(MemoryError, reader.create_volume_from_tiffs, self.test_dir)

    def testLoadVolume(self):
        expected_data = np.full((5, 4, 3), [0, 127, 255], np.uint8)
        size = np.ones(3)
        centre = np.zeros(3)
        histogram = np.histogram(expected_data, bins=256)
        volume = Volume(expected_data, size, centre, histogram)
        writer.write_volume_as_images(self.test_dir, volume)
        new_volume = reader.load_volume(self.test_dir, size, centre)
        self.assertEqual(new_volume.data.dtype, np.uint8)
        np.testing.assert_array_equal(new_volume.data, expected_data)
        np.testing.assert_array_equal(new_volume.histogram[0], histogram[0])
        np.testing.assert_array_equal(new_volume.histogram[1], histogram[1])
        self.assertIs(new_volume.data, new_volume.render_target)
        np.testing.assert_array_equal(new_volume.voxel_size, size)
        np.testing.assert_array_equal(new_volume.transform_matrix[:3, 3], centre)

        binned_data = np.full((4, 3, 2), [0, 255], np.uint8)
        histogram = np.histogram(binned_data, bins=256)
        size = [1., 1.5, 2.0]
        centre = [1, 1, 1]
        new_volume = reader.load_volume(self.test_dir, size, centre, max_bytes=10, max_dim=4)
        self.assertEqual(new_volume.data.dtype, np.uint8)
        np.testing.assert_array_equal(new_volume.data, expected_data)
        self.assertIsNot(new_volume.data, new_volume.render_target)
        np.testing.assert_array_equal(new_volume.render_target, binned_data)
        np.testing.assert_array_equal(new_volume.histogram[0], histogram[0])
        np.testing.assert_array_equal(new_volume.histogram[1], histogram[1])
        np.testing.assert_array_equal(new_volume.voxel_size, size)
        np.testing.assert_array_equal(new_volume.transform_matrix[:3, 3], centre)

        data2 = np.full((5, 4, 3), [-0.5, 0, 0.5], np.float32).transpose()
        # Check that error is thrown when arrays don't match
        nxs_data = {
            'entry/data/data/x': [0, 1, 2],
            'entry/data/data/y': [3, 4, 5, 6],
            'entry/data/data/z': [6, 7, 8, 9, 10],
            'entry/data/data/data': data2,
            'entry/data/definition': b'NXtomoproc',
            'entry/definition': b'TOFRAW'
        }
        filename = os.path.join(self.test_dir, "test.h5")
        h = h5py.File(str(filename), 'w')
        for key, value in nxs_data.items():
            h.create_dataset(str(key), data=value)
        h['entry'].attrs['NX_class'] = u'NXentry'
        h.close()

        new_volume = reader.load_volume(filename, max_bytes=10, max_dim=4)
        np.testing.assert_equal(new_volume.data, expected_data.transpose())
        np.testing.assert_array_almost_equal(new_volume.voxel_size, np.ones(3), decimal=5)
        np.testing.assert_array_almost_equal(new_volume.transform_matrix[:3, 3], [1.0, 4.5, 8.0], decimal=5)
        np.testing.assert_array_equal(new_volume.render_target, binned_data.transpose())
        np.testing.assert_array_equal(new_volume.histogram[0], histogram[0])
        np.testing.assert_array_equal(new_volume.histogram[1], histogram[1])

        # self.assertEqual(new_volume.data.dtype, np.uint8)
        # np.testing.assert_array_equal(new_volume.data, expected_data)
        # self.assertIsNot(new_volume.data, new_volume.render_target)
        # np.testing.assert_array_equal(new_volume.render_target, binned_data)
        # np.testing.assert_array_equal(new_volume.histogram[0], histogram[0])
        # np.testing.assert_array_equal(new_volume.histogram[1], histogram[1])
        # np.testing.assert_array_equal(new_volume.voxel_size, size)
        # np.testing.assert_array_equal(new_volume.transform_matrix[:3, 3], centre)

    def testReadObj(self):
        # Write Obj file
        obj = ("# Demo\n"
               "v 0.5 0.5 0.0\n"
               "v -0.5 0.0 0.0\n"
               "v 0.0 0.0 0.0\n"
               "\n"
               "usemtl material_0\n"
               "f 1//1 2//2 3//3\n"
               "\n"
               "# End of file")

        filename = self.writeTestFile("test.obj", obj)

        vertices = np.array([[0.5, 0.5, 0.0], [-0.5, 0.0, 0.0], [0.0, 0.0, 0.0]])
        normals = np.array([[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]])

        mesh = reader.read_3d_model(filename)
        np.testing.assert_array_almost_equal(mesh.vertices[mesh.indices], vertices, decimal=5)
        np.testing.assert_array_almost_equal(mesh.normals[mesh.indices], normals, decimal=5)

    def testReadAsciiStl(self):
        # Write STL file
        stl = ("solid STL generated for demo\n"
               "facet normal 0.0 0.0 1.0\n"
               "  outer loop\n"
               "    vertex  0.5 0.5 0.0\n"
               "    vertex  -0.5 0.0 0.0\n"
               "    vertex  0.0 0.0 0.0\n"
               "  endloop\n"
               "endfacet\n"
               "endsolid demo\n")

        filename = self.writeTestFile("test.stl", stl)
        with open(filename, "w") as stl_file:
            stl_file.write(stl)

        # cleaning the mesh will result in sorted vertices
        vertices = np.array([[-0.5, 0.0, 0.0], [0.0, 0.0, 0.0], [0.5, 0.5, 0.0]])
        normals = np.array([[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]])

        mesh = reader.read_3d_model(filename)
        np.testing.assert_array_almost_equal(mesh.vertices, vertices, decimal=5)
        np.testing.assert_array_almost_equal(mesh.normals, normals, decimal=5)
        np.testing.assert_array_equal(mesh.indices, np.array([2, 0, 1]))

    def testReadAndWriteBinaryStl(self):
        vertices = np.array([[1, 2, 0], [4, 5, 0], [7, 28, 0]])
        normals = np.array([[0, 0, 1], [0, 0, 1], [0, 0, 1]])
        indices = np.array([0, 1, 2])
        mesh_to_write = Mesh(vertices, indices, normals)
        full_path = os.path.join(self.test_dir, "test.stl")
        writer.write_binary_stl(full_path, mesh_to_write)

        mesh_read_from_file = reader.read_3d_model(full_path)
        np.testing.assert_array_almost_equal(mesh_to_write.vertices, mesh_read_from_file.vertices, decimal=5)
        np.testing.assert_array_almost_equal(mesh_to_write.normals, mesh_read_from_file.normals, decimal=5)
        np.testing.assert_array_equal(mesh_to_write.indices, mesh_read_from_file.indices)

    def testReadCsv(self):
        csvs = [
            "1.0, 2.0, 3.0\n4.0, 5.0, 6.0\n7.0, 8.0, 9.0\n",
            "1.0\t 2.0,3.0\n4.0, 5.0\t 6.0\n7.0, 8.0, 9.0\n",
            "1.0\t 2.0\t 3.0\n4.0\t 5.0\t 6.0\n7.0\t 8.0\t 9.0\n\n",
        ]

        for csv in csvs:
            filename = self.writeTestFile("test.csv", csv)

            data = reader.read_csv(filename)
            expected = [["1.0", "2.0", "3.0"], ["4.0", "5.0", "6.0"], ["7.0", "8.0", "9.0"]]

            np.testing.assert_array_equal(data, expected)

        filename = self.writeTestFile("test.csv", "")
        self.assertRaises(ValueError, reader.read_csv, filename)

    def testReadPoints(self):
        csv = "1.0, 2.0, 3.0\n4.0, 5.0, 6.0\n7.0, 8.0, 9.0\n"
        filename = self.writeTestFile("test.csv", csv)
        data = reader.read_points(filename)
        expected = ([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]], [True, True, True])
        np.testing.assert_array_equal(data[1], expected[1])
        np.testing.assert_array_almost_equal(data[0], expected[0], decimal=5)

        csv = "1.0, 2.0, 3.0, false\n4.0, 5.0, 6.0, True\n7.0, 8.0, 9.0\n"
        filename = self.writeTestFile("test.csv", csv)
        data = reader.read_points(filename)
        expected = ([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]], [False, True, True])
        np.testing.assert_array_equal(data[1], expected[1])
        np.testing.assert_array_almost_equal(data[0], expected[0], decimal=5)

        csv = "1.0, 3.9, 2.0, 3.0, false\n4.0, 5.0, 6.0, True\n7.0, 8.0, 9.0\n"  # first point has 4 values
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_points, filename)

        points = np.rec.array(
            [([11.0, 12.0, 13.0], True), ([14.0, 15.0, 16.0], False), ([17.0, 18.0, 19.0], True)],
            dtype=[("points", "f4", 3), ("enabled", "?")],
        )
        filename = os.path.join(self.test_dir, "test.csv")
        writer.write_points(filename, points)
        data, state = reader.read_points(filename)
        np.testing.assert_array_equal(state, points.enabled)
        np.testing.assert_array_almost_equal(data, points.points, decimal=5)

        points.enabled[1] = True
        filename = os.path.join(self.test_dir, "test.csv")
        writer.write_points(filename, points)
        data, state = reader.read_points(filename)
        np.testing.assert_array_equal(state, points.enabled)
        np.testing.assert_array_almost_equal(data, points.points, decimal=5)

        csv = "nan, 2.0, 3.0, false\n4.0, 5.0, 6.0, True\n7.0, 8.0, 9.0\n"  # first point has NAN
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_points, filename)

    def testReadAngles(self):
        csv = "xyz\n1.0, 2.0, 3.0\n4.0, 5.0, 6.0\n7.0, 8.0, 9.0\n"
        filename = self.writeTestFile("test.csv", csv)
        data = reader.read_angles(filename)
        expected = ([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]], "xyz")
        np.testing.assert_array_equal(data[1], expected[1])
        np.testing.assert_array_almost_equal(data[0], expected[0], decimal=5)

        csv = "1.0, 2.0, 3.0\n4.0, 5.0, 6.0\n7.0, 8.0, 9.0\n"  # missing order
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_angles, filename)

        csv = "xyz\n1.0, 2.0\n4.0, 5.0, 6.0\n7.0, 8.0, 9.0\n"  # missing order
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_angles, filename)

        csv = "zyx\nnan, 2.0, 3.0\n4.0, 5.0, 6.0\n7.0, 8.0, 9.0\n"  # first point has NAN
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_angles, filename)

    def testReadVectors(self):
        # measurement vector column size must be a multiple of 3
        csv = "1.0, 2.0, 3.0,4.0\n, 1.0, 2.0, 3.0,4.0\n1.0, 2.0, 3.0,4.0\n1.0, 2.0, 3.0,4.0\n"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_vectors, filename)

        # NAN in data
        csv = "1.0,2.0,3.0,4.0,nan,6.0\n,1.0,2.0,3.0,4.0,5.0,6.0\n1.0,2.0,3.0,4.0,5.0,6.0\n\n"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_vectors, filename)

        # second and third row missing data
        csv = "1.0, 2.0, 3.0,4.0, 5.0, 6.0\n, 1.0, 2.0, 3.0,4.0\n1.0, 2.0, 3.0,4.0\n1.0, 2.0, 3.0,4.0\n"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_vectors, filename)

        csv = "1.0,2.0,3.0,4.0,5.0,6.0\n,1.0,2.0,3.0,4.0,5.0,6.0\n1.0,2.0,3.0,4.0,5.0,6.0\n\n"
        filename = self.writeTestFile("test.csv", csv)
        data = reader.read_vectors(filename)
        expected = [[1.0, 2.0, 3.0, 4.0, 5.0, 6.0], [1.0, 2.0, 3.0, 4.0, 5.0, 6.0], [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]]
        np.testing.assert_array_almost_equal(data, expected, decimal=5)

        csv = "1.0,2.0,3.0\n,1.0,2.0,3.0\n1.0,2.0,3.0\n"
        filename = self.writeTestFile("test.csv", csv)
        data = reader.read_vectors(filename)
        expected = [[1.0, 2.0, 3.0], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0]]
        np.testing.assert_array_almost_equal(data, expected, decimal=5)

    def testReadRobotWorldCalibrationFile(self):
        csv = "1,0,0,0,a,0\n1,0,0,0,50,prismatic,0"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_robot_world_calibration_file, filename)
        csv = "1,0,0,0\n1,0,0,0"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_robot_world_calibration_file, filename)
        csv = "1,0,0,0\n1,0,0,0,5"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_robot_world_calibration_file, filename)
        csv = "1,6,69.9,52.535,Nan,0,0,0\n"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_robot_world_calibration_file, filename)
        csv = ("1,6,69.9,52.535,-583.339,0,0,0\n"
               "2,4,12.972,62.343,-423.562,90,-90,50\n"
               "3,1,42.946,74.268,-329.012,-90,90,-50")
        filename = self.writeTestFile("test.csv", csv)
        data = reader.read_robot_world_calibration_file(filename)
        np.testing.assert_array_equal(data[0], [0, 1, 2])
        np.testing.assert_array_almost_equal(data[1], [5, 3, 0])
        np.testing.assert_array_almost_equal(
            data[2], [[69.9, 52.535, -583.339], [12.972, 62.343, -423.562], [42.946, 74.268, -329.012]], decimal=5)
        np.testing.assert_array_almost_equal(data[3], [[0, 0, 0], [90, -90, 50], [-90, 90, -50]], decimal=5)

    def testReadKinematicCalibrationFile(self):
        csv = "1,0,0,0,a,0\n1,0,0,0,50,prismatic,0"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_kinematic_calibration_file, filename)
        csv = "1,0,0,0,a,prismatic,0\n1,0,0,0,50,prismatic,0"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_kinematic_calibration_file, filename)
        csv = "1,0,0,0,0,prismatic,0\n1,0,0,0,50,prismatic,0"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_kinematic_calibration_file, filename)
        csv = "1,0,0,0,0,prismatic,0\n1,0,0,0,50,prismatic,0\n1,0,0,0,100,prismatis,0\n"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_kinematic_calibration_file, filename)
        csv = "1,0,0,0,0,prismatis,0\n1,0,0,0,50,prismatis,0\n1,0,0,0,100,prismatis,0\n"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_kinematic_calibration_file, filename)
        csv = "1,0,0,0,0,prismatic,10\n1,0,0,0,50,prismatic,0\n1,0,0,0,100,prismatic,0\n"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_kinematic_calibration_file, filename)
        csv = ("1,0,0,0,0,prismatic,0\n1,0,0,0,50,prismatic,0\n1,0,0,0,100,prismatic,0\n"
               "2,1.1,1.1,1.1,1,revolute,1\n2,1.1,1.1,1.1,51,revolute,1\n2,1.1,1.1,1.1,101,revolute,1")
        filename = self.writeTestFile("test.csv", csv)
        points, types, offsets, homes = reader.read_kinematic_calibration_file(filename)

        self.assertListEqual(types, [Link.Type.Prismatic, Link.Type.Revolute])
        np.testing.assert_array_almost_equal(homes, [0, 1], decimal=5)
        np.testing.assert_array_almost_equal(points[0], np.zeros((3, 3)), decimal=5)
        np.testing.assert_array_almost_equal(points[1], np.ones((3, 3)) * 1.1, decimal=5)
        np.testing.assert_array_almost_equal(offsets[0], [0, 50, 100], decimal=5)
        np.testing.assert_array_almost_equal(offsets[1], [1, 51, 101], decimal=5)

    def testReadTransMatrix(self):
        csv = "1.0, 2.0, 3.0,4.0\n, 1.0, 2.0, 3.0,4.0\n1.0, 2.0, 3.0,4.0\n1.0, 2.0, 3.0,4.0\n"
        filename = self.writeTestFile("test.csv", csv)
        data = reader.read_trans_matrix(filename)
        expected = [[1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0]]
        np.testing.assert_array_almost_equal(data, expected, decimal=5)

        csv = "1.0, 2.0, 3.0,4.0\n, 1.0, 2.0, 3.0,4.0\n1.0, 2.0, 3.0,4.0\n"  # missing last row
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_trans_matrix, filename)

        csv = "1.0, 2.0, 3.0,4.0\n, 1.0, 2.0, 3.0,4.0\n1.0, 2.0, 3.0,4.0\n1.0, 2.0, 3.0,inf\n"  # INF in data
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_trans_matrix, filename)

        csv = "1.0, 2.0, 3.0\n, 1.0, 2.0, 3.0,4.0\n1.0, 2.0, 3.0,4.0\n1.0, 2.0, 3.0,4.0\n"  # incorrect col size
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_trans_matrix, filename)

    def testReadFpos(self):
        expected = np.array([
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
        ])
        expected_indices = np.array([0, 1, 2, 3])
        filename = os.path.join(self.test_dir, "test.csv")
        writer.write_fpos(filename, expected_indices, expected[:, 0:3], expected[:, 3:])
        index, points, pose = reader.read_fpos(filename)
        with open(filename, "r") as text_file:
            indices_plus_one = text_file.read().split()[::8]
            np.testing.assert_equal(np.array(indices_plus_one, int), expected_indices + 1)

        np.testing.assert_equal(index, expected_indices)
        np.testing.assert_array_almost_equal(points, expected[:, 0:3], decimal=5)
        np.testing.assert_array_almost_equal(pose, expected[:, 3:], decimal=5)

        expected_indices = np.array([8, 0, 2, 5])
        writer.write_fpos(filename, expected_indices, expected[:, 0:3])
        index, points, pose = reader.read_fpos(filename)
        np.testing.assert_equal(index, expected_indices)
        np.testing.assert_array_almost_equal(points, expected[:, 0:3], decimal=5)
        self.assertEqual(pose.size, 0)
        with open(filename, "r") as text_file:
            indices_plus_one = text_file.read().split()[::4]
            np.testing.assert_equal(np.array(indices_plus_one, int), expected_indices + 1)

        csv = "1.0, 2.0, 3.0\n, 1.0, 2.0, 3.0\n1.0, 2.0, 3.0\n"  # missing index column
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_fpos, filename)

        csv = ("9, 1.0, 2.0, 3.0, 5.0\n, 1, 1.0, 2.0, 3.0\n, "
               "3, 1.0, 2.0, 3.0\n, 6, 1.0, 2.0, 3.0\n")  # incorrect col size
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_fpos, filename)

        csv = "1, nan, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0\n, 2, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0\n"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_fpos, filename)

        csv = "1, 1.0, 2.0, 3.0, 4.0, 5.0, -inf, 7.0\n, 2, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0\n"
        filename = self.writeTestFile("test.csv", csv)
        self.assertRaises(ValueError, reader.read_fpos, filename)

    def testValidateVectorLength(self):
        vectors = np.ones((3, 3, 2))
        self.assertFalse(reader.validate_vector_length(vectors))

        vectors = np.zeros((3, 3, 2))
        self.assertTrue(reader.validate_vector_length(vectors))

        vectors[:, :, 0] = [
            [0.0000076, 1.0000000, 0.0000480],
            [0.0401899, 0.9659270, 0.2556752],
            [0.1506346, 0.2589932, 0.9540607],
        ]

        vectors[:, :, 1] = [
            [0.1553215, -0.0000486, 0.9878640],
            [0.1499936, -0.2588147, 0.9542100],
            [0.0403915, -0.9658791, 0.2558241],
        ]
        self.assertTrue(reader.validate_vector_length(vectors))

        vectors = np.zeros((3, 6, 1))
        vectors[:, :3, 0] = [
            [0.0000076, 1.0000000, 0.0000480],
            [0.00000000, 0.0000000, 0.0000000],
            [0.1506346, 0.2589932, 0.9540607],
        ]

        vectors[:, 3:, 0] = [
            [0.1553215, -0.0000486, 0.9878640],
            [0.1499936, -0.2588147, 0.9542100],
            [0.0403915, -0.9658791, 0.2558241],
        ]
        self.assertTrue(reader.validate_vector_length(vectors))

        vectors[0, 0, 0] = 10
        self.assertFalse(reader.validate_vector_length(vectors))

    def writeTestFile(self, filename, text):
        full_path = os.path.join(self.test_dir, filename)
        with open(full_path, "w") as text_file:
            text_file.write(text)
        return full_path


if __name__ == "__main__":
    unittest.main()
