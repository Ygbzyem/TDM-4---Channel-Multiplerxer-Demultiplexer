# =============================================================
# vivado_single_case.tcl - run ONE case from a text file in the Vivado GUI.
#
# Reads NUM_CHANNELS / DATA_WIDTH / CH0.. from the case file, sets them on the
# simulation, runs tb_tdm_top_filebased.v to $finish, then (if Python is on the
# PATH) writes the golden-model result for the same file. Nothing is compared:
# open the two result files side by side.
#
# In the Tcl Console of an open project (src/*.v as design sources,
# techbench/tb_tdm_top_filebased.v as a simulation source):
#
#   source C:/path/to/repo/scripts/vivado_single_case.tcl
#       -> uses input/single_case.txt
#   set case_file C:/path/to/repo/input/single_case_4x16.txt
#   source C:/path/to/repo/scripts/vivado_single_case.tcl
#       -> uses the file you set
#
# Results: results/single_case/<N>x<W>/rtl_result.txt and golden_result.txt
# Use a project path without accents.
# =============================================================

set tdm_repo [file dirname [file dirname [file normalize [info script]]]]
if {![info exists case_file]} {
    set case_file [file join $tdm_repo input single_case.txt]
}
set case_file [file normalize $case_file]

# ---- read the size from the case file
set tdm_n ""
set tdm_w ""
set fp [open $case_file r]
while {[gets $fp line] >= 0} {
    regsub {//.*$} $line "" line
    regexp {^\s*NUM_CHANNELS\s*=\s*([0-9]+)} $line -> tdm_n
    regexp {^\s*DATA_WIDTH\s*=\s*([0-9]+)}   $line -> tdm_w
}
close $fp
if {$tdm_n eq "" || $tdm_w eq ""} {
    error "$case_file must contain NUM_CHANNELS = .. and DATA_WIDTH = .."
}
set out_dir [file join $tdm_repo results single_case "${tdm_n}x${tdm_w}"]
file mkdir $out_dir
puts "Case file : $case_file ($tdm_n channels x $tdm_w bits)"
puts "Results in: $out_dir"

# ---- configure the simulation: top, parameters, file paths
set sim_fs [get_filesets sim_1]
set_property top tb_tdm_top_filebased $sim_fs
set_property generic "NUM_CHANNELS=$tdm_n DATA_WIDTH=$tdm_w" $sim_fs
set sim_opts [join [list \
    -testplusarg CASE=$case_file \
    -testplusarg TRACE=$out_dir/rtl_result.txt \
    -testplusarg OUT_HEX=$out_dir/rtl_output_vectors.hex \
    -testplusarg OUT_STREAM=$out_dir/rtl_stream_vectors.txt \
    -testplusarg OUT_LAT=$out_dir/rtl_latency_vectors.txt] " "]
set_property -name {xsim.simulate.xsim.more_options} -value $sim_opts -objects $sim_fs

# ---- run the simulation to $finish
catch {close_sim -force -quiet}
launch_simulation
run all

# ---- golden model for the same case file (needs Python on the PATH)
set golden_out [file join $out_dir golden_result.txt]
set golden_py  [file join $tdm_repo golden_model single_case.py]
set golden_ok 0
foreach py {python py python3} {
    if {![catch {exec $py $golden_py --case $case_file --out $golden_out} msg]} {
        puts $msg
        set golden_ok 1
        break
    }
}
if {!$golden_ok} {
    puts "Golden model not run from Vivado. Run it in a terminal:"
    puts "  python $golden_py --case $case_file --out $golden_out"
}
puts "Compare these two files side by side:"
puts "  $out_dir/rtl_result.txt"
puts "  $golden_out"
