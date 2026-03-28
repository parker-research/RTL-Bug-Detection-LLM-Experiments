#!/bin/bash

# Prompt for constructing this tool:

# Help me categorize these benchmarks, which mostly each contain a "base" version (not buggy),
# and 1+ "buggy" versions. Sometimes, the buggy versions have descriptions of why/how they're
# buggy, and sometimes they don't. 
#
# I want you to organize these files into a structure like this:
#
# "./project_name_optional_bug_subname/base.v" and "./project_name_optional_bug_subname/buggy.v" 
#
# Write "install -D" commands (like cp, but which creates directories as needed) to copy the files
# into the destination path.
#
# Here's an example:
# Input:
# 4       benchmarks/decoder_3_to_8/decoder_3_to_8.v
# 4       benchmarks/decoder_3_to_8/decoder_3_to_8_buggy_num.v
#
# Output:
# install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8.v $OUTPUT_DIR/decoder_3_to_8_num/base.v
# install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8_buggy_num.v $OUTPUT_DIR/decoder_3_to_8_num/buggy.v
#
# Here's the full input. You may have to ignore isolated files with no base-buggy counterpart.
# You may also have to ignore testbenches and similar, as best as you can.
#
# Pasted full `du -a benchmarks | rg -v _tb` result here.

set -e 

CLONE_DIR=/tmp/cirfix
GIT_DIR=/tmp/cirfix/verilog_repair
OUTPUT_DIR=/tmp/cirfix_normalized

rm -rf $CLONE_DIR || true
rm -rf $GIT_DIR || true

mkdir -p $CLONE_DIR
cd $CLONE_DIR
# Check out the Cirfix repository at `main` as of these experiments (commit 8219cd0).
git clone https://github.com/hammad-a/verilog_repair
cd $GIT_DIR

mkdir -p $OUTPUT_DIR

# Note: We use `install -D` as it makes the necessary parent directories as needed.

# decoder_3_to_8
install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8.v $OUTPUT_DIR/decoder_3_to_8_buggy_num/base.v
install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8_buggy_num.v $OUTPUT_DIR/decoder_3_to_8_buggy_num/buggy.v

install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8.v $OUTPUT_DIR/decoder_3_to_8_buggy_var/base.v
install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8_buggy_var.v $OUTPUT_DIR/decoder_3_to_8_buggy_var/buggy.v

install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8.v $OUTPUT_DIR/decoder_3_to_8_kgoliya_buggy1/base.v
install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8_kgoliya_buggy1.v $OUTPUT_DIR/decoder_3_to_8_kgoliya_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8.v $OUTPUT_DIR/decoder_3_to_8_super_buggy/base.v
install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8_super_buggy.v $OUTPUT_DIR/decoder_3_to_8_super_buggy/buggy.v

install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8.v $OUTPUT_DIR/decoder_3_to_8_wadden_buggy1/base.v
install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8_wadden_buggy1.v $OUTPUT_DIR/decoder_3_to_8_wadden_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8.v $OUTPUT_DIR/decoder_3_to_8_wadden_buggy2/base.v
install -D $GIT_DIR/benchmarks/decoder_3_to_8/decoder_3_to_8_wadden_buggy2.v $OUTPUT_DIR/decoder_3_to_8_wadden_buggy2/buggy.v

# first_counter_overflow
install -D $GIT_DIR/benchmarks/first_counter_overflow/first_counter_overflow.v $OUTPUT_DIR/first_counter_buggy_all/base.v
install -D $GIT_DIR/benchmarks/first_counter_overflow/first_counter_buggy_all.v $OUTPUT_DIR/first_counter_buggy_all/buggy.v

install -D $GIT_DIR/benchmarks/first_counter_overflow/first_counter_overflow.v $OUTPUT_DIR/first_counter_buggy_counter/base.v
install -D $GIT_DIR/benchmarks/first_counter_overflow/first_counter_buggy_counter.v $OUTPUT_DIR/first_counter_buggy_counter/buggy.v

install -D $GIT_DIR/benchmarks/first_counter_overflow/first_counter_overflow.v $OUTPUT_DIR/first_counter_buggy_overflow/base.v
install -D $GIT_DIR/benchmarks/first_counter_overflow/first_counter_buggy_overflow.v $OUTPUT_DIR/first_counter_buggy_overflow/buggy.v

install -D $GIT_DIR/benchmarks/first_counter_overflow/first_counter_overflow.v $OUTPUT_DIR/first_counter_kgoliya_buggy1/base.v
install -D $GIT_DIR/benchmarks/first_counter_overflow/first_counter_overflow_kgoliya_buggy1.v $OUTPUT_DIR/first_counter_kgoliya_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/first_counter_overflow/first_counter_overflow.v $OUTPUT_DIR/first_counter_wadden_buggy1/base.v
install -D $GIT_DIR/benchmarks/first_counter_overflow/first_counter_overflow_wadden_buggy1.v $OUTPUT_DIR/first_counter_wadden_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/first_counter_overflow/first_counter_overflow.v $OUTPUT_DIR/first_counter_wadden_buggy2/base.v
install -D $GIT_DIR/benchmarks/first_counter_overflow/first_counter_overflow_wadden_buggy2.v $OUTPUT_DIR/first_counter_wadden_buggy2/buggy.v

# flip_flop (tff)
install -D $GIT_DIR/benchmarks/flip_flop/tff.v $OUTPUT_DIR/tff_wadden_buggy1/base.v
install -D $GIT_DIR/benchmarks/flip_flop/tff_wadden_buggy1.v $OUTPUT_DIR/tff_wadden_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/flip_flop/tff.v $OUTPUT_DIR/tff_wadden_buggy2/base.v
install -D $GIT_DIR/benchmarks/flip_flop/tff_wadden_buggy2.v $OUTPUT_DIR/tff_wadden_buggy2/buggy.v

# fsm_full
install -D $GIT_DIR/benchmarks/fsm_full/fsm_full.v $OUTPUT_DIR/fsm_full_buggy_num/base.v
install -D $GIT_DIR/benchmarks/fsm_full/fsm_full_buggy_num.v $OUTPUT_DIR/fsm_full_buggy_num/buggy.v

install -D $GIT_DIR/benchmarks/fsm_full/fsm_full.v $OUTPUT_DIR/fsm_full_buggy_var/base.v
install -D $GIT_DIR/benchmarks/fsm_full/fsm_full_buggy_var.v $OUTPUT_DIR/fsm_full_buggy_var/buggy.v

install -D $GIT_DIR/benchmarks/fsm_full/fsm_full.v $OUTPUT_DIR/fsm_full_ssscrazy_buggy1/base.v
install -D $GIT_DIR/benchmarks/fsm_full/fsm_full_ssscrazy_buggy1.v $OUTPUT_DIR/fsm_full_ssscrazy_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/fsm_full/fsm_full.v $OUTPUT_DIR/fsm_full_ssscrazy_buggy2/base.v
install -D $GIT_DIR/benchmarks/fsm_full/fsm_full_ssscrazy_buggy2.v $OUTPUT_DIR/fsm_full_ssscrazy_buggy2/buggy.v

install -D $GIT_DIR/benchmarks/fsm_full/fsm_full.v $OUTPUT_DIR/fsm_full_super_buggy/base.v
install -D $GIT_DIR/benchmarks/fsm_full/fsm_full_super_buggy.v $OUTPUT_DIR/fsm_full_super_buggy/buggy.v

install -D $GIT_DIR/benchmarks/fsm_full/fsm_full.v $OUTPUT_DIR/fsm_full_wadden_buggy1/base.v
install -D $GIT_DIR/benchmarks/fsm_full/fsm_full_wadden_buggy1.v $OUTPUT_DIR/fsm_full_wadden_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/fsm_full/fsm_full.v $OUTPUT_DIR/fsm_full_wadden_buggy2/base.v
install -D $GIT_DIR/benchmarks/fsm_full/fsm_full_wadden_buggy2.v $OUTPUT_DIR/fsm_full_wadden_buggy2/buggy.v

# lshift_reg
install -D $GIT_DIR/benchmarks/lshift_reg/lshift_reg.v $OUTPUT_DIR/lshift_reg_buggy_num/base.v
install -D $GIT_DIR/benchmarks/lshift_reg/lshift_reg_buggy_num.v $OUTPUT_DIR/lshift_reg_buggy_num/buggy.v

install -D $GIT_DIR/benchmarks/lshift_reg/lshift_reg.v $OUTPUT_DIR/lshift_reg_buggy_var/base.v
install -D $GIT_DIR/benchmarks/lshift_reg/lshift_reg_buggy_var.v $OUTPUT_DIR/lshift_reg_buggy_var/buggy.v

install -D $GIT_DIR/benchmarks/lshift_reg/lshift_reg.v $OUTPUT_DIR/lshift_reg_kgoliya_buggy1/base.v
install -D $GIT_DIR/benchmarks/lshift_reg/lshift_reg_kgoliya_buggy1.v $OUTPUT_DIR/lshift_reg_kgoliya_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/lshift_reg/lshift_reg.v $OUTPUT_DIR/lshift_reg_wadden_buggy1/base.v
install -D $GIT_DIR/benchmarks/lshift_reg/lshift_reg_wadden_buggy1.v $OUTPUT_DIR/lshift_reg_wadden_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/lshift_reg/lshift_reg.v $OUTPUT_DIR/lshift_reg_wadden_buggy2/base.v
install -D $GIT_DIR/benchmarks/lshift_reg/lshift_reg_wadden_buggy2.v $OUTPUT_DIR/lshift_reg_wadden_buggy2/buggy.v

# mux_4_1
install -D $GIT_DIR/benchmarks/mux_4_1/mux_4_1.v $OUTPUT_DIR/mux_4_1_buggy_var/base.v
install -D $GIT_DIR/benchmarks/mux_4_1/mux_4_1_buggy_var.v $OUTPUT_DIR/mux_4_1_buggy_var/buggy.v

install -D $GIT_DIR/benchmarks/mux_4_1/mux_4_1.v $OUTPUT_DIR/mux_4_1_kgoliya_buggy1/base.v
install -D $GIT_DIR/benchmarks/mux_4_1/mux_4_1_kgoliya_buggy1.v $OUTPUT_DIR/mux_4_1_kgoliya_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/mux_4_1/mux_4_1.v $OUTPUT_DIR/mux_4_1_wadden_buggy1/base.v
install -D $GIT_DIR/benchmarks/mux_4_1/mux_4_1_wadden_buggy1.v $OUTPUT_DIR/mux_4_1_wadden_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/mux_4_1/mux_4_1.v $OUTPUT_DIR/mux_4_1_wadden_buggy2/base.v
install -D $GIT_DIR/benchmarks/mux_4_1/mux_4_1_wadden_buggy2.v $OUTPUT_DIR/mux_4_1_wadden_buggy2/buggy.v

# opencores/i2c — i2c_master_bit_ctrl
install -D $GIT_DIR/benchmarks/opencores/i2c/i2c_master_bit_ctrl.v $OUTPUT_DIR/i2c_master_bit_ctrl_kgoliya_buggy1/base.v
install -D $GIT_DIR/benchmarks/opencores/i2c/i2c_master_bit_ctrl_kgoliya_buggy1.v $OUTPUT_DIR/i2c_master_bit_ctrl_kgoliya_buggy1/buggy.v

# opencores/i2c — i2c_master_top
install -D $GIT_DIR/benchmarks/opencores/i2c/i2c_master_top.v $OUTPUT_DIR/i2c_master_top_buggy/base.v
install -D $GIT_DIR/benchmarks/opencores/i2c/i2c_master_top_buggy.v $OUTPUT_DIR/i2c_master_top_buggy/buggy.v

install -D $GIT_DIR/benchmarks/opencores/i2c/i2c_master_top.v $OUTPUT_DIR/i2c_master_top_buggy_v2/base.v
install -D $GIT_DIR/benchmarks/opencores/i2c/i2c_master_top_buggy_v2.v $OUTPUT_DIR/i2c_master_top_buggy_v2/buggy.v

install -D $GIT_DIR/benchmarks/opencores/i2c/i2c_master_top.v $OUTPUT_DIR/i2c_master_top_more_buggy/base.v
install -D $GIT_DIR/benchmarks/opencores/i2c/i2c_master_top_more_buggy.v $OUTPUT_DIR/i2c_master_top_more_buggy/buggy.v

# opencores/i2c — i2c_slave_model
install -D $GIT_DIR/benchmarks/opencores/i2c/i2c_slave_model.v $OUTPUT_DIR/i2c_slave_model_wadden_buggy1/base.v
install -D $GIT_DIR/benchmarks/opencores/i2c/i2c_slave_model_wadden_buggy1.v $OUTPUT_DIR/i2c_slave_model_wadden_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/opencores/i2c/i2c_slave_model.v $OUTPUT_DIR/i2c_slave_model_wadden_buggy2/base.v
install -D $GIT_DIR/benchmarks/opencores/i2c/i2c_slave_model_wadden_buggy2.v $OUTPUT_DIR/i2c_slave_model_wadden_buggy2/buggy.v

# opencores/pairing — tate_pairing
install -D $GIT_DIR/benchmarks/opencores/pairing/tate_pairing.v $OUTPUT_DIR/tate_pairing_buggy/base.v
install -D $GIT_DIR/benchmarks/opencores/pairing/tate_pairing_buggy.v $OUTPUT_DIR/tate_pairing_buggy/buggy.v

install -D $GIT_DIR/benchmarks/opencores/pairing/tate_pairing.v $OUTPUT_DIR/tate_pairing_buggy_v2/base.v
install -D $GIT_DIR/benchmarks/opencores/pairing/tate_pairing_buggy_v2.v $OUTPUT_DIR/tate_pairing_buggy_v2/buggy.v

install -D $GIT_DIR/benchmarks/opencores/pairing/tate_pairing.v $OUTPUT_DIR/tate_pairing_kgoliya_buggy1/base.v
install -D $GIT_DIR/benchmarks/opencores/pairing/tate_pairing_kgoliya_buggy1.v $OUTPUT_DIR/tate_pairing_kgoliya_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/opencores/pairing/tate_pairing.v $OUTPUT_DIR/tate_pairing_wadden_buggy1/base.v
install -D $GIT_DIR/benchmarks/opencores/pairing/tate_pairing_wadden_buggy1.v $OUTPUT_DIR/tate_pairing_wadden_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/opencores/pairing/tate_pairing.v $OUTPUT_DIR/tate_pairing_wadden_buggy2/base.v
install -D $GIT_DIR/benchmarks/opencores/pairing/tate_pairing_wadden_buggy2.v $OUTPUT_DIR/tate_pairing_wadden_buggy2/buggy.v

# opencores/reed_solomon_decoder — BM_lamda
install -D $GIT_DIR/benchmarks/opencores/reed_solomon_decoder/BM_lamda.v $OUTPUT_DIR/BM_lamda_ssscrazy_buggy1/base.v
install -D $GIT_DIR/benchmarks/opencores/reed_solomon_decoder/BM_lamda_ssscrazy_buggy1.v $OUTPUT_DIR/BM_lamda_ssscrazy_buggy1/buggy.v

# opencores/reed_solomon_decoder — out_stage
install -D $GIT_DIR/benchmarks/opencores/reed_solomon_decoder/out_stage.v $OUTPUT_DIR/out_stage_buggy/base.v
install -D $GIT_DIR/benchmarks/opencores/reed_solomon_decoder/out_stage_buggy.v $OUTPUT_DIR/out_stage_buggy/buggy.v

install -D $GIT_DIR/benchmarks/opencores/reed_solomon_decoder/out_stage.v $OUTPUT_DIR/out_stage_buggy_v2/base.v
install -D $GIT_DIR/benchmarks/opencores/reed_solomon_decoder/out_stage_buggy_v2.v $OUTPUT_DIR/out_stage_buggy_v2/buggy.v

install -D $GIT_DIR/benchmarks/opencores/reed_solomon_decoder/out_stage.v $OUTPUT_DIR/out_stage_ssscrazy_buggy1/base.v
install -D $GIT_DIR/benchmarks/opencores/reed_solomon_decoder/out_stage_ssscrazy_buggy1.v $OUTPUT_DIR/out_stage_ssscrazy_buggy1/buggy.v

# opencores/reed_solomon_decoder — RS_dec
install -D $GIT_DIR/benchmarks/opencores/reed_solomon_decoder/RS_dec.v $OUTPUT_DIR/RS_dec_buggy/base.v
install -D $GIT_DIR/benchmarks/opencores/reed_solomon_decoder/RS_dec_buggy.v $OUTPUT_DIR/RS_dec_buggy/buggy.v

install -D $GIT_DIR/benchmarks/opencores/reed_solomon_decoder/RS_dec.v $OUTPUT_DIR/RS_dec_buggy_v2/base.v
install -D $GIT_DIR/benchmarks/opencores/reed_solomon_decoder/RS_dec_buggy_v2.v $OUTPUT_DIR/RS_dec_buggy_v2/buggy.v

# opencores/sha3 — f_permutation
install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/f_permutation.v $OUTPUT_DIR/f_permutation_buggy/base.v
install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/f_permutation_buggy.v $OUTPUT_DIR/f_permutation_buggy/buggy.v

install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/f_permutation.v $OUTPUT_DIR/f_permutation_buggy_v2/base.v
install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/f_permutation_buggy_v2.v $OUTPUT_DIR/f_permutation_buggy_v2/buggy.v

install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/f_permutation.v $OUTPUT_DIR/f_permutation_buggy_v3/base.v
install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/f_permutation_buggy_v3.v $OUTPUT_DIR/f_permutation_buggy_v3/buggy.v

install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/f_permutation.v $OUTPUT_DIR/f_permutation_kgoliya_buggy1/base.v
install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/f_permutation_kgoliya_buggy1.v $OUTPUT_DIR/f_permutation_kgoliya_buggy1/buggy.v

# opencores/sha3 — keccak
install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/keccak.v $OUTPUT_DIR/keccak_kgoliya_buggy1/base.v
install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/keccak_kgoliya_buggy1.v $OUTPUT_DIR/keccak_kgoliya_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/keccak.v $OUTPUT_DIR/keccak_wadden_buggy1/base.v
install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/keccak_wadden_buggy1.v $OUTPUT_DIR/keccak_wadden_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/keccak.v $OUTPUT_DIR/keccak_wadden_buggy2/base.v
install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/keccak_wadden_buggy2.v $OUTPUT_DIR/keccak_wadden_buggy2/buggy.v

# opencores/sha3 — padder
install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/padder.v $OUTPUT_DIR/padder_ssscrazy_buggy1/base.v
install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/padder_ssscrazy_buggy1.v $OUTPUT_DIR/padder_ssscrazy_buggy1/buggy.v

# opencores/sha3 — round
install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/round.v $OUTPUT_DIR/round_ssscrazy_buggy1/base.v
install -D $GIT_DIR/benchmarks/opencores/sha3/low_throughput_core/round_ssscrazy_buggy1.v $OUTPUT_DIR/round_ssscrazy_buggy1/buggy.v

# sdram_controller
install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller.v $OUTPUT_DIR/sdram_controller_buggy_num/base.v
install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller_buggy_num.v $OUTPUT_DIR/sdram_controller_buggy_num/buggy.v

install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller.v $OUTPUT_DIR/sdram_controller_buggy_v2/base.v
install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller_buggy_v2.v $OUTPUT_DIR/sdram_controller_buggy_v2/buggy.v

install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller.v $OUTPUT_DIR/sdram_controller_buggy_var/base.v
install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller_buggy_var.v $OUTPUT_DIR/sdram_controller_buggy_var/buggy.v

install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller.v $OUTPUT_DIR/sdram_controller_githubbug/base.v
install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller_githubbug.v $OUTPUT_DIR/sdram_controller_githubbug/buggy.v

install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller.v $OUTPUT_DIR/sdram_controller_kgoliya_buggy2/base.v
install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller_kgoliya_buggy2.v $OUTPUT_DIR/sdram_controller_kgoliya_buggy2/buggy.v

install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller.v $OUTPUT_DIR/sdram_controller_wadden_buggy1/base.v
install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller_wadden_buggy1.v $OUTPUT_DIR/sdram_controller_wadden_buggy1/buggy.v

install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller.v $OUTPUT_DIR/sdram_controller_wadden_buggy2/base.v
install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller_wadden_buggy2.v $OUTPUT_DIR/sdram_controller_wadden_buggy2/buggy.v

# Note: Manually exclude these files, as it is empty in the latest version.
# install -D $GIT_DIR/benchmarks/sdram_controller/sdram_controller.v $OUTPUT_DIR/sdram_controller_super_buggy/base.v
# install -D $GIT_DIR/benchmarks/sdram_controller/sd_controller_super_buggy.v $OUTPUT_DIR/sdram_controller_super_buggy/buggy.v



# Validation step:
# For each subfolder, do a "diff thatfolder/base.v thatfolder/buggy.v",
# and show the file counts and total number of lines different.
for dir in $OUTPUT_DIR/*/ ; do
    if [[ -f "$dir/base.v" && -f "$dir/buggy.v" ]]; then
        base_count=$(wc -l < "$dir/base.v")
        buggy_count=$(wc -l < "$dir/buggy.v")
        diff_count=$(diff "$dir/base.v" "$dir/buggy.v" | wc -l)
        echo "$dir: $base_count -> $buggy_count - Diff: $diff_count"
    fi
done

echo ""
echo ""
echo "Done. Now, copy files out of \"$OUTPUT_DIR\" to continue using them."
