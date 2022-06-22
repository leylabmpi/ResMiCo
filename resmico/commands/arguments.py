import argparse


def add_common_args(parser: argparse.ArgumentParser):
    """
    Adds arguments common to both training and evaluation to parser.
    """
    # default stats for n9k-train training dataset
    pkg_stats = resource_filename('resmico', 'model/stats_cov.json')
    parser.add_argument('--feature-files-path', default='.', type=str,
                        help='Path to the feature files produced by ResMiCo-SM. 2 options available:'
                             ' 1) Provide the base path, and subdirectories will be searched.'
                             ' 2) Provide a file that lists all stats files (assocaited files must be in the same directories).'
                        )
    parser.add_argument('--feature-file-match', default='', type=str,
                        help='String that paths to feature files must match '
                             '(e.g. 0.005 to select of lowest abundance contigs only)')
    parser.add_argument('--stats-file', default=pkg_stats,
                        help='File containing the feature means/stdevs of the training set.')
    parser.add_argument('--save-path', default='.', type=str,
                        help='Directory where to save output (default: %(default)s)')
    parser.add_argument('--save-name', default='resmico', type=str,
                        help='Prefix for name in the save_path (default: %(default)s)')
    parser.add_argument('--gpu-eval-mem-gb', default=3.0, type=float,
                        help='Amount of GPU memory used for validation data (amount will be divided per GPU)')
    parser.add_argument('--val-ind-f', default=None, type=str,
                        help='Validation data indices (default: %(default)s)')
    parser.add_argument('--log-level', default='INFO',
                        help='Logging level, one of [CRITICAL, FATAL, ERROR, WARNING, INFO, DEBUG]')
    parser.add_argument('--no-cython', dest='no_cython', action='store_true',
                        help='If set, data is read using pure Python rather than using the Cython bindings '
                             '(about 2x slower, only useful for debugging)')
    parser.add_argument('--seed', default=12, type=int,
                        help='Seed used for numpy.random and tf (default: %(default)s)')
    parser.add_argument('--n-procs', default=1, type=int,
                        help='Number of parallel processes (default: %(default)s)')
    parser.add_argument('--max-len', default=10000, type=int,
                        help='Max contig length, otherwise chunks of this size are cutted')
    parser.add_argument('--save-path', default='.', type=str,
                        help='Directory where to save output (default: %(default)s)')
    parser.add_argument('--save-name', default='resmico', type=str,
                        help='Prefix for name in the save_path (default: %(default)s)')
    parser.add_argument('--features', nargs='+', help='Features to use for training', default=[
        'num_query_A',
        'num_query_C', 
        'num_query_G', 
        'num_query_T',
        'mean_mapq_Match',
        'stdev_al_score_Match',
        'mean_al_score_Match',
        'mean_insert_size_Match',
        'coverage',
        'min_al_score_Match',
        'num_SNPs',
        'min_insert_size_Match',
        'num_proper_Match',
        'num_orphans_Match'
    ])
    parser.add_argument('--mask-padding', default=False,
                        help='If enabled, values affected by padding will be masked out in the convolution output',
                        dest='mask_padding', action='store_true')
    parser.add_argument('--min-avg-coverage', default=1.0, type=float,
                        help='Minimum average coverage for a contig to be considered during evaluation or training')
