from __future__ import print_function
from pkg_resources import resource_filename
import os
import argparse
import logging
from resmico import bam2feat

# functions
def get_desc():
    desc = 'Convert >=1 contig fasta + mapped-reads BAM to a feature table'
    return desc

def parse_args(test_args=None, subparsers=None):
    desc = get_desc()
    epi = """DESCRIPTION:
    Convert >=1 contig fasta and associated mapped paired-end reads (BAM file)
    to >=1 resmico feature table.
    The input_table maps the fasta and BAM files.
    The defaults are the same as used to generate all training/test data in the
    Mineeva et al., 2022 manuscript.
    --n-proc sets the per-BAM parallelization.
    --n-threads sets the per-command (eg., samtools) parallelization.
    """
    if subparsers:
        parser = subparsers.add_parser('bam2feat', description=desc, epilog=epi,
                                       formatter_class=argparse.RawTextHelpFormatter)
    else:
        parser = argparse.ArgumentParser(description=desc, epilog=epi,
                                         formatter_class=argparse.RawTextHelpFormatter)
    # args
    parser.add_argument('input_table', type=str, 
                        help='A tab-delim table with the columns: Taxon,Fasta,Sample,BAM.\n'
                        'The columns can be in any order; capitalization does not matter.\n'
                        'Taxon: name associated with the fasta file\n'
                        'Sample: name associated with the BAM file\n')
    parser.add_argument('--outdir', default='resmico-bam2feat', type=str, 
                        help='Output directory (default: %(default)s)')
    parser.add_argument('--tmpdir', default='resmico-bam2feat_TMP', type=str, 
                        help='Temporary file directory (default: %(default)s)')
    parser.add_argument('--max-coverage', default=20.0, type=float, 
                        help='Subsample mapped reads to this max coverage per-contig'
                        ' (default: %(default)s)')
    parser.add_argument('--window', default=6, type=int, 
                        help='Sliding window size for sequence entropy & GC content'
                        ' (default: %(default)s)')
    parser.add_argument('--breakpoint-margin', default=50, type=int,
                        help='Maximum offset (to left or right) around the breaking point\n'
                        'used when creating a chunk (default: %(default)s)')
    parser.add_argument('--queue-size', default=32, type=int,
                        help='Maximum size of the queue for stats waiting to be written to disk,\n'
                        'before blocking (default: %(default)s)')
    parser.add_argument('--seed', default=8192, type=int, 
                        help='Seed for reproducible subsampling (default: %(default)s)')
    parser.add_argument('--n-proc', default=1, type=int, 
                        help='No. of BAM files to process in parallel (default: %(default)s)')
    parser.add_argument('--n-threads', default=1, type=int, 
                        help='No. threads to pass to samtools & bam2feat (default: %(default)s)')
    
    # test args
    if test_args:
        args = parser.parse_args(test_args)
        return args
    # return
    return parser

def main(args=None):
    logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.DEBUG)
    # Input
    if args is None:
        args = parse_args()
        print()
        print (args)
        print()
    # Main interface
    bam2feat.main(args)
    
# main
if __name__ == '__main__':
    pass


