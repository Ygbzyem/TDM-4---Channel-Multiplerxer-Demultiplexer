# =============================================================
# vivado_single_case.tcl - run ONE case from a text file in the Vivado GUI.
#
# A case gives every device a whole message (hex); the testbench cuts it into
# DATA_WIDTH-bit slots and sends slot f of every channel in frame f.
# Reads NUM_CHANNELS / DATA_WIDTH / CH0.. from the case file, sets them on the
# simulation, runs tb_tdm_top_filebased.v to $finish, then (if Python is on the
# PATH) writes the golden-model result for the same file. Nothing is compared:
# open the two result files side by side.
#
# In the Tcl Console of an open project (src/*.v as design sources,
# techbench/tb_tdm_top_filebased.v as a simulation source):
#
#   source C:/path/to/repo/scripts/vivado_single_case.tcl
#       -> uses input/message_case.txt
#   set case_file C:/path/to/repo/input/message_case_4x16.txt
#   source C:/path/to/repo/scripts/vivado_single_case.tcl
#       -> uses the file you set
#
# Results: results/single_case/<case file name>/rtl_result.txt and golden_result.txt
# Use a project path without accents.
# =============================================================

set tdm_repo [file dirname [file dirname [file normalize [info script]]]]
if {![info exists case_file]} {
    set case_file [file join $tdm_repo input message_case.txt]
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
set out_dir [file join $tdm_repo results single_case [file rootname [file tail $case_file]]]
file mkdir $out_dir
puts "Case file : $case_file ($tdm_n channels x $tdm_w bits)"
puts "Results in: $out_dir"

# ---- the project must use the parameterized sources of this repository
set sim_fs [get_filesets sim_1]
set tdm_problems {}
set tdm_checks [list \
    "simulation source" sim_1     tb_tdm_top_filebased.v [file join $tdm_repo techbench tb_tdm_top_filebased.v] \
    "design source"     sources_1 tdm_top.v              [file join $tdm_repo src tdm_top.v]]
foreach {kind fs name want} $tdm_checks {
    set found ""
    foreach f [get_files -quiet -of_objects [get_filesets $fs]] {
        if {[file tail $f] eq $name} { set found $f }
    }
    if {$found eq ""} {
        lappend tdm_problems "$name is not a $kind of this project"
        continue
    }
    set fh [open $found r]
    set txt [read $fh]
    close $fh
    if {![string match *NUM_CHANNELS* $txt]} {
        lappend tdm_problems "the project uses an old $name (no NUM_CHANNELS parameter): $found"
    }
}
if {[llength $tdm_problems]} {
    foreach p $tdm_problems { puts "PROBLEM: $p" }
    puts "Use the files of the repository $tdm_repo. In this Tcl console:"
    puts "  remove_files \[get_files -of_objects \[get_filesets sources_1\] *.v\]"
    puts "  remove_files \[get_files -quiet -of_objects \[get_filesets sim_1\] *.v\]"
    puts "  add_files -norecurse \[glob $tdm_repo/src/*.v\]"
    puts "  add_files -fileset sim_1 -norecurse \[list $tdm_repo/techbench/tb_tdm_top_filebased.v $tdm_repo/techbench/tb_tdm_top.v\]"
    puts "  update_compile_order -fileset sources_1"
    puts "  update_compile_order -fileset sim_1"
    puts "then source this script again."
    error "the Vivado project does not use the parameterized sources (see PROBLEM lines above)"
}

# ---- configure the simulation: top, parameters, file paths
set_property top tb_tdm_top_filebased $sim_fs
set_property generic "NUM_CHANNELS=$tdm_n DATA_WIDTH=$tdm_w" $sim_fs
set sim_opts [join [list \
    -testplusarg CASE=$case_file \
    -testplusarg TRACE=$out_dir/rtl_result.txt] " "]
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
