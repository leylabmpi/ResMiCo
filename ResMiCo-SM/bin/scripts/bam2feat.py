#!/usr/bin/env python
# import
## batteries
import sys,os
import copy
import argparse
import logging
import itertools
import statistics
from math import log
from random import shuffle
from functools import partial
from collections import deque, defaultdict
from multiprocessing import Pool
## 3rd party
import pysam

# logging
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.DEBUG)
class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass

# argparse
desc = 'Creating DL features from bam file'
epi = """DESCRIPTION:
The bam file should be indexed via `samtools index`.
The fasta file should be indexed via `samtools faidx`.

The '--short' list of features is the features used for
DeepMAsED version1. Using '--short' will generate a 
feature table that is much smaller (many fewer features).

The output tab-delimited feature table is written to STDOUT.
"""
parser = argparse.ArgumentParser(description=desc,
                                 epilog=epi,
                                 formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('bam_file', metavar='bam_file', type=str,
                    help='bam (or sam) file')
parser.add_argument('fasta_file', metavar='fasta_file', type=str,
                    help='Reference sequences for the bam (sam) file')
parser.add_argument('-a', '--assembler', type=str, default='unknown',
                    help='Name of metagenome assembler used to create the contigs')
parser.add_argument('-b', '--batches', type=int, default=100,
                    help='Number of contigs batches for parallel processing')
parser.add_argument('-c', '--chunks', type=int, default=50,
                    help='No. of bins to process before writing; lower values = lower memory')
parser.add_argument('-p', '--procs', type=int, default=1,
                    help='Number of parallel processes (default: %(default)s)')
parser.add_argument('-w', '--window', type=int, default=4,
                    help='Sliding window size for sequence entropy & GC content')
parser.add_argument('-s', '--short', action='store_true', default=False,
                    help='Short feature list instead of all features?')
parser.add_argument('--debug', action='store_true', default=False,
                    help='Debug mode; just for troubleshooting')
parser.add_argument('--version', action='version', version='0.0.1')


# global 
IDX = {'A':0, 'C':1, 'G':2, 'T':3, 'N':-1}

# functions
def count_SNPs(coverage_by_base, ref_seq):
    """
    Count SNPs across the reference
    
    Params:
      coverage_by_base : pysam.AlignmentFile.count_coverage object
      ref_seq : py.FastaFile.fetch object
    Return
      int
    """
    SNP_cnt = 0
    for i,x in enumerate(coverage_by_base):
        if i != IDX[ref_seq]:
            SNP_cnt += x[0]
    return SNP_cnt

def entropy(seq):
    """
    Calculate Shannon entropy of sequence.
    """
    cnt = [seq.count(i) for i in 'ACGT']
    d = sum(cnt)
    if d == 0:
        return 0
    ent = []
    for i in [float(i)/d for i in cnt]:
        # round corner case that would cause math domain error
        if i == 0:
            i = 1
        ent.append(i * log(i, 2))
    ent = abs(-1 * sum(ent))
    return round(ent, 3)

def gc_percent(seq):
    """ 
    Calculate fraction of GC bases within sequence.
    """
    counts = [seq.count(i) for i in 'ACGT']
    scounts = sum(counts)
    if scounts == 0:
        return 0
    gc = float(counts[1] + counts[2])/scounts
    return round(gc, 3)

def window(seq, wsize = 4):
    """
    Sliding window of sequence
    """
    it = iter(seq)
    win = deque((next(it, None) for _ in range(wsize)), maxlen=wsize)
    yield win
    append = win.append
    for e in it:
        append(e)
        yield win

def seq_entropy(seq, window_size):
    """
    Calculate the sequence entropy across a sliding window
    
    Params:
      seq : py.FastaFile.fetch object
      window_size : int
    Return:
      sequence_entropy (float), sequence_G+C (float)
    """
    if window_size > int(len(seq)/2.0):
        window_size = int(len(seq)/2.0)
        
    ent = []
    gc = []
    # 1st half (forward)
    midpoint = int(len(seq)/2.0)
    seq_sub = seq[:midpoint + window_size - 1]
    for x in window(seq_sub, window_size):
        ent.append(entropy(x))
        gc.append(gc_percent(x))
    # 2nd half (reverse)
    seq_sub = seq[:midpoint - window_size:-1]
    ent_tmp = []
    gc_tmp = []
    for x in window(seq_sub, window_size):
        ent_tmp.append(entropy(x))
        gc_tmp.append(gc_percent(x))
    ent += ent_tmp[::-1]
    gc += gc_tmp[::-1]
    
    return ent, gc
    
def _contig_stats(contig, bam_file, fasta_file, assembler, window_size, short):
    """ 
    Extracting contig-specific info from bam file.
    
    Params:
      See contig_stats()
    Returns:
      [contig1_stats, ..., contigN_stats]
    """
    logging.info('  Processing contig: {}'.format(contig))
    
    fasta = pysam.FastaFile(fasta_file)    
    x = 'rb' if bam_file.endswith('.bam') else 'r'

    stats = []
    with pysam.AlignmentFile(bam_file, x) as inF:
        # ref (contig)
        contig_i = inF.references.index(contig)
        ref_seq = fasta.fetch(contig)
        # sequence entropy & GC content along a sliding window
        seq_ents,gc_percs = seq_entropy(fasta.fetch(contig, 0,
                                                    inF.lengths[contig_i]),
                                        window_size)        
        # the BP in which each read has a SNP
        logging.info('    Creating SNP index')
        query_SNP = defaultdict(dict)
        for pileupcolumn in inF.pileup(contig, 0, inF.lengths[contig_i], min_base_quality=1, min_mapping_quality=1, ignore_overlaps=False):
            ref_base = ref_seq[pileupcolumn.reference_pos] 
            for pileupread in pileupcolumn.pileups:
                # print(pileupcolumn.reference_pos)
                if not pileupread.is_del and not pileupread.is_refskip:
                    query_base = pileupread.alignment.query_sequence[pileupread.query_position]
                    query_SNP[pileupcolumn.reference_pos][pileupread.alignment.query_name] = \
                      ref_base != query_base
                else:
                    query_SNP[pileupcolumn.reference_pos][pileupread.alignment.query_name] = True

        # read alignment at each position
        logging.info('    Getting per-read characteristics')                
        contig_len = inF.lengths[contig_i]
        for pos in range(0, contig_len):
            if (pos + 1) % 5000 == 0:
                logging.info('      {} of {} positions complete'.format(pos+1, contig_len))
            # ref base at position
            ref_base = ref_seq[pos:pos+1]
            # coverage at position
            coverage_by_base = inF.count_coverage(contig, pos, pos+1)
            SNPs = count_SNPs(coverage_by_base, ref_base)
            coverage = sum([x[0] for x in coverage_by_base])
            # sequence entropy
            seq_ent = seq_ents[pos]
            gc_perc = gc_percs[pos]
            # reads
            read_stats = {'n_proper' : 0,
                          'n_orphan' : 0,
                          'n_sup' : 0,
                          'n_sec' : 0,                        
                          'n_diff_strand' : 0,
                          'n_discord' : 0,
                          'i_sizes' : [],
                          'map_quals' : []}
            read_stats = {True : copy.deepcopy(read_stats),   # SNP
                          False : copy.deepcopy(read_stats)}  # match
            ## iterating per-read
            n_discord = 0
            for read in inF.fetch(contig, pos, pos+1):
                # is the read a SNP at that position?
                try:
                    is_SNP = query_SNP[pos][read.query_name]
                except KeyError:
                    is_SNP = False

                # read qualities
                if read.is_paired == True and read.is_unmapped == False:
                    if (read.is_proper_pair == False and
                        read.mate_is_unmapped == False):
                        read_stats[is_SNP]['n_discord'] += 1
                        n_discord += 1
                    elif (read.is_proper_pair == True and
                        read.mate_is_unmapped == False):
                        read_stats[is_SNP]['n_proper'] += 1
                    elif (read.mate_is_unmapped == False and
                          read.is_reverse != read.mate_is_reverse):
                        read_stats[is_SNP]['n_diff_strand'] += 1
                    elif read.mate_is_unmapped == True:
                        read_stats[is_SNP]['n_orphan'] += 1
                    ## insert size
                    read_stats[is_SNP]['i_sizes'].append(abs(read.template_length))
                ## sup/sec reads
                if read.is_supplementary:
                    read_stats[is_SNP]['n_sup'] += 1
                if read.is_secondary:
                    read_stats[is_SNP]['n_sec'] += 1
                ## mapping quality
                read_stats[is_SNP]['map_quals'].append(read.mapping_quality)
                    
            # aggretation
            if not short:
                for SNP_match in [True, False]:
                    # insert sizes
                    try:
                        i_sizes = read_stats[SNP_match]['i_sizes']
                        read_stats[SNP_match]['min_i_size'] = min(i_sizes)
                        read_stats[SNP_match]['mean_i_size']  = round(statistics.mean(i_sizes),1)
                        read_stats[SNP_match]['max_i_size'] = max(i_sizes)
                    except ValueError:
                        read_stats[SNP_match]['min_i_size'] = 'NA'
                        read_stats[SNP_match]['mean_i_size'] = 'NA'
                        read_stats[SNP_match]['max_i_size'] = 'NA'
                    try:
                        read_stats[SNP_match]['stdev_i_size'] = round(statistics.stdev(i_sizes),1)
                    except ValueError:
                        read_stats[SNP_match]['stdev_i_size'] = 'NA'
                    # MAPQ
                    try:
                        map_quals = read_stats[SNP_match]['map_quals']
                        read_stats[SNP_match]['min_map_qual'] = min(map_quals)
                        read_stats[SNP_match]['mean_map_qual']  = \
                           round(statistics.mean(map_quals),1)
                        read_stats[SNP_match]['max_map_qual'] = max(map_quals)
                    except ValueError:
                        read_stats[SNP_match]['min_map_qual'] = 'NA'
                        read_stats[SNP_match]['mean_map_qual'] = 'NA'
                        read_stats[SNP_match]['max_map_qual'] = 'NA'
                    try:
                        read_stats[SNP_match]['stdev_map_qual'] = \
                          round(statistics.stdev(map_quals),1)
                    except ValueError:
                        read_stats[SNP_match]['stdev_map_qual'] = 'NA'
                        
            # columns
            x = [
                assembler,                    # assembler ID
                contig,                       # contig ID
                str(pos),                     # position (bp)
                # SNPs & coverage
                ref_base,                     # base at position                
                str(coverage_by_base[0][0]),  # number of reads with 'A'
                str(coverage_by_base[1][0]),  # number of reads with 'C'
                str(coverage_by_base[2][0]),  # number of reads with 'G'
                str(coverage_by_base[3][0]),  # number of reads with 'T'
                str(SNPs),                    # number of SNPs (relative to base at position)
                str(coverage),                # total reads at position
                str(n_discord)                # total discordant reads (for rev-compatibility)
                ]
            if not short:
                x += [
                    # characterization of reads matching the reference at this position
                    str(read_stats[False]['min_i_size']),
                    str(read_stats[False]['mean_i_size']),
                    str(read_stats[False]['stdev_i_size']),
                    str(read_stats[False]['max_i_size']),
                    str(read_stats[False]['min_map_qual']),
                    str(read_stats[False]['mean_map_qual']),
                    str(read_stats[False]['stdev_map_qual']),
                    str(read_stats[False]['max_map_qual']),
                    str(read_stats[False]['n_proper']),
                    str(read_stats[False]['n_diff_strand']),
                    str(read_stats[False]['n_orphan']),
                    str(read_stats[False]['n_sup']),
                    str(read_stats[False]['n_sec']),
                    str(read_stats[False]['n_discord']),
                    # characterization of reads with SNP vs ref at this position
                    str(read_stats[True]['min_i_size']),
                    str(read_stats[True]['mean_i_size']),
                    str(read_stats[True]['stdev_i_size']),
                    str(read_stats[True]['max_i_size']),
                    str(read_stats[True]['min_map_qual']),
                    str(read_stats[True]['mean_map_qual']),
                    str(read_stats[True]['stdev_map_qual']),
                    str(read_stats[True]['max_map_qual']),
                    str(read_stats[True]['n_proper']),
                    str(read_stats[True]['n_diff_strand']),
                    str(read_stats[True]['n_orphan']),
                    str(read_stats[True]['n_sup']),
                    str(read_stats[True]['n_sec']),
                    str(read_stats[True]['n_discord'])
                    ]
            # general seq info
            x += [
                str(seq_ent),             # sliding window sequence entropy
                str(gc_perc)              # sliding window percent GC
            ]
            stats.append(x)
            
        return stats
    
def contig_stats(contigs, bam_file, fasta_file, assembler, window_size, short):
    """ 
    Extracting contig-specific info from all contigs
    
    Params:
      contigs : pysam.AlignmentFile.references object
      bam_file : str; bam file path
      fasta_file : str; bam file path
      assembler : str; which assembler used?
      window_size : int; window size for calculating window-based stats
      short : bool; just short feature list?
    Returns:
      [contig1_stats, ..., contigN_stats]
    """
    stats = []
    for contig in contigs:
        x = _contig_stats(contig, bam_file, fasta_file,
                          assembler, window_size, short)
        stats.append(x)
    return stats

def batch_contigs(contigs, n_batches):
    """
    Processing contigs in batches. 
    
    Params: 
      contigs : pysam.AlignmentFile.references object
      n_batches : int; number of batch

    Returns:
      dict : {bin_id : [contig1, ..., contigN]}
    """
    n_contigs = len(contigs)
    if n_contigs < n_batches:
        n_batches = n_contigs
    n_per_batch = int(round(n_contigs / float(n_batches), 0))
    msg = 'Batching {} contigs into {} equal bins (~{} per bin)'
    logging.info(msg.format(n_contigs, n_batches, n_per_batch))
    
    contig_bins = {}
    contigs = list(contigs)
    shuffle(contigs)
    for contig,_bin in zip(contigs, itertools.cycle(range(0,n_batches))):
        try:
            contig_bins[_bin].append(contig)
        except KeyError:
            contig_bins[_bin] = [contig]
    return list(contig_bins.values())

def write_stats(stats):
    """
    Pretty print of the results
    """
    logging.info('Writing features...')
    for batch in stats:
        for y in batch:
            for z in y:
                print('\t'.join(z))

def main(args):
    """ 
    Main interface
    """
    # output table header
    H = ['assembler', 'contig',  'position', 'ref_base', 
         'num_query_A', 'num_query_C', 'num_query_G', 'num_query_T',
         'num_SNPs', 'coverage', 'num_discordant']
    if not args.short:
        H += [
         'min_insert_size_Match',
         'mean_insert_size_Match',
         'stdev_insert_size_Match',
         'max_insert_size_Match',
         'min_mapq_Match',
         'mean_mapq_Match',
         'stdev_mapq_Match',
         'max_mapq_Match',         
         'num_proper_Match',
         'num_diff_strand_Match',
         'num_orphans_Match',
         'num_supplementary_Match',
         'num_secondary_Match',
         'num_discordant_Match',
         'min_insert_size_SNP',
         'mean_insert_size_SNP',
         'stdev_insert_size_SNP',
         'max_insert_size_SNP',
         'min_mapq_SNP',
         'mean_mapq_SNP',
         'stdev_mapq_SNP',
         'max_mapq_SNP',         
         'num_proper_SNP',
         'num_diff_strand_SNP',
         'num_orphans_SNP',
         'num_supplementary_SNP',
         'num_secondary_SNP',
         'num_discordant_SNP']
    H += ['seq_window_entropy', 'seq_window_perc_gc']
    print('\t'.join(H))
    
    # Getting contig list
    x = 'rb' if args.bam_file.endswith('.bam') else 'r'
    contigs = []
    with pysam.AlignmentFile(args.bam_file, x) as inF:
        contigs = inF.references
    msg = 'Number of contigs in the bam file: {}'
    logging.info(msg.format(len(contigs)))

    # debug (just smallest 10 contigs)
    if args.debug:
        contigs = contigs[len(contigs)-10:]
    
    # getting contig stats (in parallel)
    func = partial(contig_stats, bam_file=args.bam_file,
                   fasta_file=args.fasta_file,
                   assembler=args.assembler,
                   window_size=args.window,
                   short=args.short)
    if args.debug is False and args.procs > 1:
        # with parallel processing
        p = Pool(args.procs)
        # batching contigs for multiprocessing
        contig_bins = batch_contigs(contigs, args.batches)
        # getting stats
        x = 0
        msg = 'Processing {} batches: {} to {}'
        for i in range(int(len(contig_bins) / args.chunks) + 1):
            i = (i + 1) * args.chunks
            i = len(contig_bins) if i >= len(contig_bins) else i
            try:
                contig_bins_p = contig_bins[x:i]
            except IndexError:
                contig_bins_p = contig_bins[x:]
            if len(contig_bins_p) == 0:
                continue
            logging.info(msg.format(len(contig_bins_p), x+1, i))
            stats = p.map(func, contig_bins_p)
            write_stats(stats)
            x = i
            stats = None
    else:
        # no parallel processing
        stats = map(func, [contigs])
        write_stats(stats)
        

if __name__ == '__main__':
    args = parser.parse_args()
    main(args)

