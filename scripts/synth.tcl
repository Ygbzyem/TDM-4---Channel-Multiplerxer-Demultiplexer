# Vivado batch synthesis of tdm_top, with utilization and timing reports.
#
#   vivado -mode batch -source scripts/synth.tcl
#
# Run it from any folder: paths are resolved relative to this script. Reports are written to results/.
# Part and clock match the numbers in README Section 9 (Vivado 2020.2, Kintex-7 xc7k70tfbv676-1).
# Use a project path without accents/special characters.

set script_dir [file dirname [file normalize [info script]]]
set root       [file dirname $script_dir]
set out_dir    [file join $root results]
file mkdir $out_dir

set part xc7k70tfbv676-1

read_verilog [glob -directory [file join $root src] *.v]
read_xdc     [file join $root constraint constraints.xdc]

synth_design -top tdm_top -part $part

report_utilization    -file [file join $out_dir utilization_synth.rpt]
report_timing_summary -file [file join $out_dir timing_synth.rpt]
write_checkpoint -force   [file join $out_dir tdm_top_synth.dcp]

puts "Reports written to $out_dir"
