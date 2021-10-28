import numpy as np
import unittest
from unittest.mock import patch, MagicMock

from resmico import Models_FL
from resmico import ContigReader
from resmico import Reader

from resmico.ContigReader import ContigInfo


class TestBinaryDatasetTrain(unittest.TestCase):
    def test_select_intervals(self):
        contig_data = [ContigInfo('Contig1', '/tmp/c1', 1000, 0, 0, 0, []),
                       ContigInfo('Contig2', '/tmp/c2', 1000, 0, 0, 0, [(100, 100)]),
                       ContigInfo('Contig3', '/tmp/c3', 1000, 0, 0, 0, [(800, 900)])]
        max_len = 500
        for i in range(50):
            intervals = Models_FL.BinaryDatasetTrain.select_intervals(contig_data, max_len, True)
            self.assertTrue(0 <= intervals[0][0] <= 500)
            self.assertTrue(500 <= intervals[0][1] <= 1000)
            self.assertTrue(0 <= intervals[1][0] <= 50)
            self.assertTrue(500 <= intervals[1][1] <= 550)
            self.assertTrue(450 <= intervals[2][0] <= 500, f'Start is {intervals[2][0]}')
            self.assertTrue(500 <= intervals[2][1] <= 1000)

    def test_select_intervals_translate_short(self):
        contig_data = [
            ContigInfo('Contig1', '/tmp/c1', 300, 0, 0, 0, [(200, 210)]),
        ]
        max_len = 350
        for i in range(50):
            intervals = Models_FL.BinaryDatasetTrain.select_intervals(contig_data, max_len, True)
            if intervals[0][1] - intervals[0][0] < 300:  # contig was truncated to left
                self.assertTrue(0 <= intervals[0][0] <= 150)
                self.assertEqual(300, intervals[0][1])
            else:  # contig will be shifted to left
                self.assertTrue(0 <= intervals[0][0] <= 50)
                self.assertEqual(300 + intervals[0][0], intervals[0][1],
                                 f'Intervals are: {intervals[0][0]}  {intervals[0][1]}')

    @patch('resmico.Models_FL.BinaryDatasetTrain.select_intervals')
    def test_contig_selection(self, mock_intervals):
        """
        Make sure that the returned contig features (when using translations) are correct.

        The test mocks reader.read_contigs and BinaryDatasetTrain.select_intervals, and checks if the returned
        (x,y) tuple of BinaryDatasetTrain.__get_item__() is correct.
        """
        for use_cython in [False, True]:
            for cached in [False, True]:
                features = ['num_query_A', 'coverage', 'num_SNPs']
                reader = ContigReader.ContigReader('data/preprocess/', features, 1, use_cython)
                c1 = ContigInfo('Contig1', '/tmp/c1', 500, 0, 0, 0, [])
                c2 = ContigInfo('Contig2', '/tmp/c2', 300, 0, 0, 1, [(100, 100)])
                c3 = ContigInfo('Contig3', '/tmp/c3', 1000, 0, 0, 1, [(800, 900)])
                reader.contigs = [c1, c2, c3]

                contigs_data = []
                st = 0
                for c in reader.contigs:
                    contig_data = {}
                    for f in features:
                        feature_data = np.arange(start=st, stop=st + c.length, dtype=float)
                        contig_data[f] = feature_data
                        st += c.length
                    contigs_data.append(contig_data)
                reader.read_contigs = MagicMock(
                    return_value=[contigs_data[0], contigs_data[1], contigs_data[1], contigs_data[1], contigs_data[2],
                                  contigs_data[2], contigs_data[2]])

                indices = np.arange(len(reader))
                batch_size = 10
                num_translations = 3
                max_len = 500
                data_gen = Models_FL.BinaryDatasetTrain(reader, indices, batch_size, features, max_len,
                                                        num_translations, 1.0, cached, False)
                data_gen.indices.sort()  # indices will now be 0,1,1,1,2,2,2
                self.assertEqual(7, len(data_gen.indices))
                mock_intervals.return_value = [(200, 700),  # 1st contig, shifted to right 200 positions
                                               (0, 300), (50, 300), (40, 340),  # 2nd contig
                                               (500, 1000), (450, 950), (440, 940)  # 3rd contig
                                               ]

                x, y = data_gen.__getitem__(0)
                self.assertEqual((batch_size, max_len, len(features)), x.shape)
                self.assertIsNone(np.testing.assert_array_equal([0, 1, 1, 1, 1, 1, 1, 0, 0, 0], y))

                # first contig
                for i in range(300):
                    self.assertEqual(i, x[0][i+200][0])
                    self.assertEqual(500 + i, x[0][i+200][1])
                    self.assertEqual(1000 + i, x[0][i+200][2])
                for i in range(200):
                    for j in range(3):
                        self.assertEqual(0, x[0][i][j])
                # 2nd contig 1st translation
                for i in range(300):
                    self.assertEqual(1500 + i, x[1][i][0])
                    self.assertEqual(1800 + i, x[1][i][1])
                    self.assertEqual(2100 + i, x[1][i][2])
                for i in range(300, 500):
                    for j in range(3):
                        self.assertEqual(0, x[1][i][j])

                # 2nd contig 2nd translation (truncate 50 bases from the left)
                for i in range(250):
                    self.assertEqual(1550 + i, x[2][i][0])
                    self.assertEqual(1850 + i, x[2][i][1])
                    self.assertEqual(2150 + i, x[2][i][2])
                for i in range(250, 500):
                    for j in range(3):
                        self.assertEqual(0, x[2][i][j])

                # 2nd contig 3rd translation (shift 40 bases to the right)
                for i in range(40):  # first 40 positions are zero
                    for j in range(3):
                        self.assertEqual(0, x[3][i][j])
                for i in range(300):  # positions 40-340 contain the actual contig data
                    self.assertEqual(1500 + i, x[3][40 + i][0])
                    self.assertEqual(1800 + i, x[3][40 + i][1])
                    self.assertEqual(2100 + i, x[3][40 + i][2])
                for i in range(340, 500):  # positions 340+ are again zero
                    for j in range(3):
                        self.assertEqual(0, x[3][i][j])

                # 3rd contig 1st translation (last 500 bases of contig 3)
                for i in range(500):
                    self.assertEqual(2900 + i, x[4][i][0])
                    self.assertEqual(3900 + i, x[4][i][1])
                    self.assertEqual(4900 + i, x[4][i][2])

                # 3rd contig 2nd translation (bases 450 to 950 of contig 3)
                for i in range(500):
                    self.assertEqual(2850 + i, x[5][i][0])
                    self.assertEqual(3850 + i, x[5][i][1])
                    self.assertEqual(4850 + i, x[5][i][2])

                # 3rd contig 3rd translation (bases 440 to 940 of contig 3)
                for i in range(500):
                    self.assertEqual(2840 + i, x[6][i][0])
                    self.assertEqual(3840 + i, x[6][i][1])
                    self.assertEqual(4840 + i, x[6][i][2])

                for idx in range(7, 10):
                    for i in range(500):
                        for j in range(3):
                            self.assertEqual(0, x[idx][i][j])

    def test_gen_train_data(self):
        for cached in [False, True]:
            reader = ContigReader.ContigReader('data/preprocess/', Reader.feature_names, 1, False)
            indices = np.arange(len(reader))
            batch_size = 10
            num_translations = 1
            data_gen = Models_FL.BinaryDatasetTrain(reader, indices, batch_size, Reader.feature_names, 500,
                                                    num_translations, 1.0, cached, False)
            data_gen.translate_short_contigs = False  # so that we know which interval is selected
            # set these to -1 in order to enforce NOT swapping A/T and G/C (for data enhancement)
            data_gen.pos_A = data_gen.pos_ref = data_gen.pos_C = -1
            # unshuffle the indices, so that we can make assertions about the returned data
            data_gen.indices = [0, 1]
            self.assertEqual(1, len(data_gen))
            train_data, y = data_gen[0]
            # even if we only have 2 samples, the remaining are filled with zero to reach the desired batch size
            self.assertEqual(batch_size, len(train_data))

            expected_y = np.zeros(batch_size)
            expected_y[0] = 1
            self.assertIsNone(np.testing.assert_array_equal(y, expected_y))

            # # train_data[0][0] - first position in first contig, train_data[0][5] 5th position in 1st contig
            self.assertIsNone(
                np.testing.assert_array_equal(train_data[0][0][0:6], np.array([1, 0, 0, 0, 2, 1])))
            self.assertIsNone(
                np.testing.assert_array_equal(train_data[0][5][0:6], np.array([1, 0, 0, 0, 0, 0])))

            # # train_data[1][0] - first position in 2nd contig, train_data[1][5] 5th position in 2nd contig
            self.assertIsNone(
                np.testing.assert_array_equal(train_data[1][0][0:6], np.array([1, 0, 0, 0, 1, 1])))
            self.assertIsNone(
                np.testing.assert_array_equal(train_data[1][5][0:6], np.array([1, 0, 0, 0, 0, 0])))


class TestBinaryDatasetEval(unittest.TestCase):
    bytes_per_base = 10 + sum(  # 10 is the overhead also added in Models_Fl.BinaryDataEval
        [np.dtype(ft).itemsize for ft in Reader.feature_np_types])

    def test_sort_by_contig_len(self):
        """ Make sure that contigs are sorted in increasing order by length """
        reader = ContigReader.ContigReader('data/preprocess/', Reader.feature_names, 1, False)
        reader.contigs = [ContigInfo('Contig1', '/tmp/c1', 300, 0, 0, 0, []),
                          ContigInfo('Contig2', '/tmp/c2', 200, 0, 0, 0, []),
                          ContigInfo('Contig3', '/tmp/c3', 100, 0, 0, 0, [])]
        indices = np.arange(len(reader))

        gpu_memory_bytes = 1010 * self.bytes_per_base
        eval_data = Models_FL.BinaryDatasetEval(reader, indices, Reader.feature_names, 500, 250, gpu_memory_bytes,
                                                False, False)
        self.assertEqual(eval_data.indices, [2, 1, 0])

    def test_batching_one_per_batch(self):
        reader = ContigReader.ContigReader('data/preprocess/', Reader.feature_names, 1, False)
        reader.contigs = [ContigInfo('Contig1', '/tmp/c1', 1000, 0, 0, 0, []),
                          ContigInfo('Contig2', '/tmp/c2', 1000, 0, 0, 0, []),
                          ContigInfo('Contig3', '/tmp/c3', 1000, 0, 0, 0, [])]
        indices = np.arange(len(reader))

        gpu_memory_bytes = 1010 * self.bytes_per_base
        eval_data = Models_FL.BinaryDatasetEval(reader, indices, Reader.feature_names, 500, 250, gpu_memory_bytes,
                                                False, False)
        self.assertEqual(3, len(eval_data.chunk_counts))
        for i in range(len(eval_data.chunk_counts)):
            self.assertEqual(1, len(eval_data.chunk_counts[i]))
            self.assertEqual(3, eval_data.chunk_counts[i][0])

    def test_batching_multiple_per_batch(self):
        reader = ContigReader.ContigReader('data/preprocess/', Reader.feature_names, 1, False)
        reader.contigs = [ContigInfo('Contig1', 'data/preprocess/features_binary', 500, 0, 246, 0, []),
                          ContigInfo('Contig2', 'data/preprocess/features_binary', 500, 246, 183, 0, []),
                          ContigInfo('Contig3', 'data/preprocess/features_binary', 500, 0, 246, 0, [])]
        indices = np.arange(len(reader))
        gpu_memory_bytes = 1600 * self.bytes_per_base
        eval_data = Models_FL.BinaryDatasetEval(reader, indices, Reader.feature_names, 250, 200, gpu_memory_bytes,
                                                False, False)
        # check that Contig1 and Contig2 are in the first batch (with 3 chunks each) and Contig3 is in the second batch
        # (also with 3 chunks)
        # 1st batch, 2 contigs, 3 chunks each
        self.assertEqual(2, len(eval_data.chunk_counts))
        self.assertEqual(2, len(eval_data.chunk_counts[0]))
        self.assertEqual(3, eval_data.chunk_counts[0][0])
        self.assertEqual(3, eval_data.chunk_counts[0][1])
        # 2nd batch, 1 contig, 3 chunks
        self.assertEqual(1, len(eval_data.chunk_counts[1]))
        self.assertEqual(3, eval_data.chunk_counts[1][0])

        self.assertEqual(6, len(eval_data[0]))
        self.assertEqual(3, len(eval_data[1]))

    def test_gen_eval_data(self):
        for cached in [False, True]:
            reader = ContigReader.ContigReader('data/preprocess/', Reader.feature_names, 1, False)
            indices = np.arange(len(reader))
            eval_data = Models_FL.BinaryDatasetEval(reader, indices, Reader.feature_names, 500, 250, 1e6, cached, False)
            self.assertEqual(1, len(eval_data))
            self.assertEqual(2, len(eval_data.batch_list[0]))
            self.assertIsNone(
                np.testing.assert_array_equal(eval_data[0][0][0][0:6], np.array([1, 0, 0, 0, 2, 1])))
            self.assertIsNone(
                np.testing.assert_array_equal(eval_data[0][0][5][0:6], np.array([1, 0, 0, 0, 0, 0])))

            self.assertTrue(all(a == b for a, b in zip(eval_data[0][1][0][0:6], [1, 0, 0, 0, 1, 1])))
            self.assertTrue(all(a == b for a, b in zip(eval_data[0][1][5][0:6], [1, 0, 0, 0, 0, 0])))

    def test_gen_eval_data_short_window(self):
        reader = ContigReader.ContigReader('data/preprocess/', Reader.feature_names, 1, False)
        indices = np.arange(len(reader))
        eval_data = Models_FL.BinaryDatasetEval(reader, indices, Reader.feature_names, 50, 30, 1e6, False, False)
        self.assertEqual(1, len(eval_data))
        self.assertEqual(2, len(eval_data.batch_list[0]))
        # 16 for the first contig of length 500, 16 for the 2nd contig of length 500
        self.assertEqual(32, len(eval_data[0]))
        self.assertTrue(all(a == b for a, b in zip(eval_data[0][0][0][0:6], [1, 0, 0, 0, 2, 1])))
        self.assertTrue(all(a == b for a, b in zip(eval_data[0][0][5][0:6], [1, 0, 0, 0, 0, 0])))

        self.assertTrue(all(a == b for a, b in zip(eval_data[0][16][0][0:6], [1, 0, 0, 0, 1, 1])))
        self.assertTrue(all(a == b for a, b in zip(eval_data[0][16][5][0:6], [1, 0, 0, 0, 0, 0])))

    def test_group(self):
        reader = ContigReader.ContigReader('data/preprocess/', Reader.feature_names, 1, False)
        indices = np.arange(len(reader))
        total_memory_bytes = 1e6
        eval_data = Models_FL.BinaryDatasetEval(reader, indices, Reader.feature_names, 50, 30, total_memory_bytes,
                                                False, False)
        self.assertEqual(32, len(eval_data[0]))

        y = np.zeros(32)
        self.assertIsNone(
            np.testing.assert_array_equal(np.array([0, 0]), eval_data.group(y)))

        y = np.zeros(32)
        y[5] = 1
        self.assertIsNone(
            np.testing.assert_array_equal(np.array([1, 0]), eval_data.group(y)))
        y[0:15] = 1
        self.assertIsNone(
            np.testing.assert_array_equal(np.array([1, 0]), eval_data.group(y)))

        y[16] = 1
        self.assertIsNone(
            np.testing.assert_array_equal(np.array([1, 1]), eval_data.group(y)))

    def test_group_two_batches(self):
        reader = ContigReader.ContigReader('data/preprocess/', Reader.feature_names, 1, False)
        indices = np.arange(len(reader))
        eval_data = Models_FL.BinaryDatasetEval(reader, indices, Reader.feature_names, 50, 30, 500, False, False)

        self.assertEqual(2, len(eval_data))
        self.assertEqual(16, len(eval_data[0]))
        self.assertEqual(16, len(eval_data[1]))

        y = np.zeros(32)
        self.assertIsNone(
            np.testing.assert_array_equal(np.array([0, 0]), eval_data.group(y)))

        y = np.zeros(32)
        y[5] = 1
        self.assertIsNone(
            np.testing.assert_array_equal(np.array([1, 0]), eval_data.group(y)))
        y[0:15] = 1
        self.assertIsNone(
            np.testing.assert_array_equal(np.array([1, 0]), eval_data.group(y)))

        y[16] = 1
        self.assertIsNone(
            np.testing.assert_array_equal(np.array([1, 1]), eval_data.group(y)))

    def test_gen_eval_data_cached(self):
        reader = ContigReader.ContigReader('data/preprocess/', Reader.feature_names, 1, False)
        indices = np.arange(len(reader))
        eval_data = Models_FL.BinaryDatasetEval(reader, indices, Reader.feature_names, 500, 250, 1e6, True, False)
        self.assertEqual(1, len(eval_data))
        self.assertEqual(2, len(eval_data.batch_list[0]))
        self.assertTrue(all(a == b for a, b in zip(eval_data[0][0][0][0:6], [1, 0, 0, 0, 2, 1])))
        self.assertTrue(all(a == b for a, b in zip(eval_data[0][0][5][0:6], [1, 0, 0, 0, 0, 0])))

        self.assertTrue(all(a == b for a, b in zip(eval_data[0][1][0][0:6], [1, 0, 0, 0, 1, 1])))
        self.assertTrue(all(a == b for a, b in zip(eval_data[0][1][5][0:6], [1, 0, 0, 0, 0, 0])))
