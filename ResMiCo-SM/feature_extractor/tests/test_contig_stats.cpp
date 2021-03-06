#include "contig_stats.hpp"

#include <gmock/gmock.h>
#include <gtest/gtest.h>
#include <string>
namespace {

using namespace ::testing;

TEST(EntropyGC, Empty) {
    auto [entropy, gc_percent] = entropy_gc_percent({ 0, 0, 0, 0 });
    ASSERT_EQ(0, entropy);
    ASSERT_EQ(0, gc_percent);
}

TEST(EntropyGC, OneElement) {
    auto [entropy, gc_percent] = entropy_gc_percent({ 1, 0, 0, 0 });
    ASSERT_EQ(0, entropy);
    ASSERT_EQ(0, gc_percent);
}

TEST(EntropyGC, OneElementGC) {
    auto [entropy, gc_percent] = entropy_gc_percent({ 0, 0, 1, 0 });
    ASSERT_EQ(0, entropy);
    ASSERT_EQ(1, gc_percent);

    auto [entropy2, gc_percent2] = entropy_gc_percent({ 0, 1, 0, 0 });
    ASSERT_EQ(0, entropy2);
    ASSERT_EQ(1, gc_percent2);
}

TEST(EntropyGC, OneOfEach) {
    auto [entropy, gc_percent] = entropy_gc_percent({ 1, 1, 1, 1 });
    ASSERT_EQ(2, entropy);
    ASSERT_EQ(0.5, gc_percent);
}

TEST(FillEntropyGC, Empty) {
    std::vector<Stats> stats;
    fill_seq_entropy("", 4, &stats);
}

// TEST(FillEntropyGC, OneChar) {
//    std::vector<Stats> stats(1);
//    fill_seq_entropy("A", 4, &stats);
//    ASSERT_EQ(stats[0].gc_percent, 0);
//    ASSERT_EQ(stats[0].entropy, 0);
//}
//
// TEST(FillEntropyGC, OneCharC) {
//    std::vector<Stats> stats(1);
//    fill_seq_entropy("C", 4, &stats);
//    ASSERT_EQ(stats[0].gc_percent, 1);
//    ASSERT_EQ(stats[0].entropy, 0);
//}

TEST(FillEntropyGC, AllSame) {
    std::string sequence = "AAAAAAAAAAA";
    std::vector<Stats> stats(sequence.size());
    fill_seq_entropy(sequence, 4, &stats);

    for (uint32_t i = 0; i < sequence.size(); ++i) {
        ASSERT_EQ(stats[i].gc_percent, 0);
        ASSERT_EQ(stats[i].entropy, 0);
    }

    std::string sequence2 = "CCCCCCCCCCC";
    fill_seq_entropy(sequence2, 5, &stats);

    for (uint32_t i = 0; i < sequence2.size(); ++i) {
        ASSERT_EQ(stats[i].gc_percent, 1);
        ASSERT_EQ(stats[i].entropy, 0);
    }
}

TEST(FillEntropyGC, HalfAndHalf) {
    std::string sequence = "AAAATTTT";
    std::vector<Stats> stats(sequence.size());
    fill_seq_entropy(sequence, 4, &stats);

    std::vector<double> expected_entropies = { 0, 0.811278, 1, 0.811278, 0.81127, 1, 0.811278, 0 };

    for (uint32_t i = 0; i < sequence.size(); ++i) {
        ASSERT_EQ(stats[i].gc_percent, 0);
        ASSERT_NEAR(stats[i].entropy, expected_entropies[i], 0.0001);
    }

    sequence = "CCCCGGGG";
    fill_seq_entropy(sequence, 4, &stats);
    for (uint32_t i = 0; i < sequence.size(); ++i) {
        ASSERT_EQ(stats[i].gc_percent, 1);
        ASSERT_NEAR(stats[i].entropy, expected_entropies[i], 0.0001);
    }

    sequence = "AAAACCCC";
    std::vector<double> expected_gc_percent = { 0, 0.25, 0.5, 0.75, 0.25, 0.5, 0.75, 1 };
    fill_seq_entropy(sequence, 4, &stats);
    for (uint32_t i = 0; i < sequence.size(); ++i) {
        ASSERT_EQ(stats[i].gc_percent, expected_gc_percent[i]);
        ASSERT_NEAR(stats[i].entropy, expected_entropies[i], 0.0001);
    }
}

TEST(PileupBam, OneRead) {
    std::string reference(500, 'A');
    std::string reference_name = "Contig1";
    std::vector<Stats> stats = pileup_bam(reference, reference_name, "data/test1.bam");
    ASSERT_EQ(500, stats.size());
    for (uint32_t i = 0; i < 4; ++i) {
        ASSERT_EQ('A', stats[i].ref_base);
        ASSERT_EQ(1, stats[i].n_proper_match);
        ASSERT_EQ(0, stats[i].n_proper_snp);
        ASSERT_EQ(0, stats[i].n_discord);
        ASSERT_EQ(0, stats[i].n_sec);
        ASSERT_EQ(0, stats[i].n_sup);
        ASSERT_EQ(0, stats[i].n_orphan_match);
        ASSERT_EQ(0, stats[i].n_diff_strand);
        ASSERT_THAT(stats[i].n_bases, ElementsAre(1, 0, 0, 0));
        ASSERT_EQ(stats[i].gc_percent, 0);
        ASSERT_EQ(stats[i].entropy, 0);
        ASSERT_EQ(stats[i].num_snps(), 0);
        ASSERT_EQ(stats[i].coverage, 1);
        ASSERT_THAT(stats[i].al_scores, ElementsAre(-27));
    }
    for (uint32_t i = 420; i < 424; ++i) {
        ASSERT_EQ('A', stats[i].ref_base);
        ASSERT_EQ(1, stats[i].n_proper_snp);
        ASSERT_EQ(0, stats[i].n_proper_match);
        ASSERT_EQ(0, stats[i].n_discord);
        ASSERT_EQ(0, stats[i].n_sec);
        ASSERT_EQ(0, stats[i].n_sup);
        ASSERT_EQ(0, stats[i].n_orphan_match);
        ASSERT_EQ(0, stats[i].n_diff_strand);
        ASSERT_THAT(stats[i].n_bases, ElementsAre(0, 1, 0, 0));
        // because GC percent is computed in contig_stats
        ASSERT_EQ(stats[i].gc_percent, 0);
        ASSERT_EQ(stats[i].entropy, 0);
        ASSERT_EQ(stats[i].num_snps(), 1);
        ASSERT_EQ(stats[i].coverage, 1);
        ASSERT_TRUE(stats[i].al_scores.empty()); // because all positions are SNVs
    }
}

TEST(PileupBam, TwoReads) {
    std::string reference(500, 'A');
    std::string reference_name = "Contig2";
    std::vector<Stats> stats = pileup_bam(reference, reference_name, "data/test2.bam");
    ASSERT_EQ(500, stats.size());
    for (uint32_t i = 0; i < 4; ++i) {
        ASSERT_EQ('A', stats[i].ref_base);
        ASSERT_EQ(i == 0 ? 2 : 1, stats[i].n_proper_match);
        ASSERT_EQ(i == 0 ? 0 : 1, stats[i].n_proper_snp);
        ASSERT_EQ(0, stats[i].n_discord);
        ASSERT_EQ(0, stats[i].n_sec);
        ASSERT_EQ(0, stats[i].n_sup);
        ASSERT_EQ(0, stats[i].n_orphan_match);
        ASSERT_EQ(0, stats[i].n_diff_strand);
        if (i == 0) {
            ASSERT_THAT(stats[i].n_bases, ElementsAre(2, 0, 0, 0));
            ASSERT_THAT(stats[i].al_scores, ElementsAre(0, -28));
        } else {
            ASSERT_THAT(stats[i].n_bases, ElementsAre(1, 0, 1, 0));
            // only alignment scores for matches are considered, so the -28 from r002 falls out
            ASSERT_THAT(stats[i].al_scores, ElementsAre(0));
        }
        ASSERT_EQ(stats[i].gc_percent, 0);
        ASSERT_EQ(stats[i].entropy, 0);
        ASSERT_EQ(stats[i].num_snps(), i == 0 ? 0 : 1);
        ASSERT_EQ(stats[i].coverage, 2);
    }
    for (uint32_t i = 420; i < 424; ++i) {
        ASSERT_EQ('A', stats[i].ref_base);
        ASSERT_EQ(2, stats[i].n_proper_snp);
        ASSERT_EQ(0, stats[i].n_proper_match);
        ASSERT_EQ(0, stats[i].n_discord);
        ASSERT_EQ(0, stats[i].n_sec);
        ASSERT_EQ(0, stats[i].n_sup);
        ASSERT_EQ(0, stats[i].n_orphan_match);
        ASSERT_EQ(0, stats[i].n_diff_strand);
        ASSERT_THAT(stats[i].n_bases, ElementsAre(0, 1, 0, 1));
        // because GC percent is computed in contig_stats
        ASSERT_EQ(stats[i].gc_percent, 0);
        ASSERT_EQ(stats[i].entropy, 0);
        ASSERT_EQ(stats[i].num_snps(), 2);
        ASSERT_EQ(stats[i].coverage, 2);
    }
}

TEST(ContigStats, TwoReads) {
    std::string contig_name =  "Contig2";
    std::string fasta_file =  "data/test2.fa.gz";
    std::string bam_file =  "data/test2.bam";

    std::string reference_seq = get_sequence(fasta_file, contig_name);
    std::vector<Stats> stats
            = contig_stats(contig_name, reference_seq, bam_file, 4, false);
    ASSERT_EQ(500, stats.size());
    for (uint32_t i = 0; i < 5; ++i) {
        ASSERT_EQ('A', stats[i].ref_base);
        ASSERT_EQ(i == 0 ? 2 : 1, stats[i].n_proper_match);
        ASSERT_EQ(i == 0 ? 0 : 1, stats[i].n_proper_snp);
        ASSERT_EQ(0, stats[i].n_discord);
        ASSERT_EQ(0, stats[i].n_sec);
        ASSERT_EQ(0, stats[i].n_sup);
        ASSERT_EQ(0, stats[i].n_orphan_match);
        ASSERT_EQ(0, stats[i].n_diff_strand);
        if (i == 0) {
            ASSERT_THAT(stats[i].n_bases, ElementsAre(2, 0, 0, 0));
            ASSERT_EQ(stats[i].min_al_score, -28);
            ASSERT_EQ(stats[i].max_al_score, 0);
            ASSERT_EQ(stats[i].mean_al_score, -14);
        } else {
            ASSERT_THAT(stats[i].n_bases, ElementsAre(1, 0, 1, 0));
            ASSERT_EQ(stats[i].min_al_score, 0);
            ASSERT_EQ(stats[i].max_al_score, 0);
            ASSERT_EQ(stats[i].mean_al_score, 0);
        }
        ASSERT_EQ(stats[i].gc_percent, 0);
        ASSERT_EQ(stats[i].entropy, 0);
        ASSERT_EQ(stats[i].num_snps(), i == 0 ? 0 : 1);
        ASSERT_EQ(stats[i].coverage, 2);
        ASSERT_EQ(stats[i].min_map_qual, 6);
        ASSERT_EQ(stats[i].max_map_qual, i == 0 ? 7 : 6);
        ASSERT_EQ(i == 0 ? 6.5 : 6, stats[i].mean_map_qual);
    }
    for (uint32_t i = 420; i < 424; ++i) {
        ASSERT_EQ('A', stats[i].ref_base);
        ASSERT_EQ(2, stats[i].n_proper_snp);
        ASSERT_EQ(0, stats[i].n_proper_match);
        ASSERT_EQ(0, stats[i].n_discord);
        ASSERT_EQ(0, stats[i].n_sec);
        ASSERT_EQ(0, stats[i].n_sup);
        ASSERT_EQ(0, stats[i].n_orphan_match);
        ASSERT_EQ(0, stats[i].n_diff_strand);
        ASSERT_THAT(stats[i].n_bases, ElementsAre(0, 1, 0, 1));
        // because GC percent is computed in contig_stats
        ASSERT_EQ(stats[i].gc_percent, 0);
        ASSERT_EQ(stats[i].entropy, 0);
        ASSERT_EQ(stats[i].num_snps(), 2);
        ASSERT_EQ(stats[i].coverage, 2);
        ASSERT_EQ(stats[i].min_map_qual, std::numeric_limits<uint8_t>::max());
        ASSERT_EQ(stats[i].max_map_qual, std::numeric_limits<uint8_t>::max());
        ASSERT_TRUE(std::isnan(stats[i].mean_map_qual));

        // no alignment scores, because no matches (all positions are SNPs)
        ASSERT_EQ(stats[i].min_al_score, 127);
        ASSERT_TRUE(std::isnan(stats[i].mean_al_score));
        ASSERT_EQ(stats[i].max_al_score, 127);
    }
}

} // namespace
