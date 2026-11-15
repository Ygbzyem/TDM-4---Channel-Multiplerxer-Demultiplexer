# Vivado batch synthesis and implementation of tdm_top, with utilization and timing reports.
#
#   vivado -mode batch -source scripts/synth.tcl
#
# Run it from any folder: paths are resolved relative to this script. Reports are written to results/:
#   tdm_top_utilization_synth.rpt   after synthesis
#   tdm_top_utilization_impl.rpt    after place and route
#   tdm_top_timing_impl.rpt         timing summary after place and route
# Part and clock match README Section 9 (Kintex-7 xc7k70tfbv676-1, 10 ns clock in constraint/constraints.xdc).
# Pins are not assigned (no target board yet), so no bitstream is written.
# Use a project path without accents/special characters.

set script_dir [file dirname [file normalize [info script]]]
set root       [file dirname $script_dir]
set out_dir    [file join $root results]
file mkdir $out_dir

set part xc7k70tfbv676-1

read_verilog [glob -directory [file join $root src] *.v]
read_xdc     [file join $root constraint constraints.xdc]

synth_design -top tdm_top -part $part
report_utilization -file [file join $out_dir tdm_top_utilization_synth.rpt]

opt_design
place_design
route_design
report_utilization    -file [file join $out_dir tdm_top_utilization_impl.rpt]
report_timing_summary -file [file join $out_dir tdm_top_timing_impl.rpt]

puts "Reports written to $out_dir"
