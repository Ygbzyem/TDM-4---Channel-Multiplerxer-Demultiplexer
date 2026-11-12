// =============================================================
// tb_tdm_top_filebased.v
//
// File-driven testbench for tdm_top. Instead of hardcoding
// CH0..CH3 values in the testbench body (as tb_tdm_top.v does),
// this testbench reads a list of test vectors from a .hex file,
// drives them one at a time into the DUT, and writes the settled
// CH0_OUT..CH3_OUT for each vector into a result .hex file, in
// the same packed-32-bit format as the input.
//
// This does not replace tb_tdm_top.v (still 38/38 PASS on its
// own hardcoded cases) - it runs alongside it, as a separate
// entry point for regression against an external reference
// (e.g. a Python golden model that reads the same input file,
// computes its own expected output, and diffs it against the
// result file this testbench produces).
//
// SELF-CHECKING: for this design, TDM is lossless and introduces
// no transformation other than the pipeline delay - so the correct
// expected output for a vector is simply that same vector's input
// bytes, {CH0,CH1,CH2,CH3}. This testbench therefore also compares
// {CH0_OUT,CH1_OUT,CH2_OUT,CH3_OUT} against the vector it just fed
// in, and prints PASS/FAIL per vector plus a final summary - so you
// get a correct/incorrect verdict directly from this run, without
// needing an external golden model just to answer "is this right".
// A golden model is still useful if you introduce something a plain
// identity check can't catch (e.g. adding a parity/CRC bit and
// checking the receiver computed it correctly) - in that case use
// the OUTPUT_FILE this testbench writes as the "actual" side of that
// comparison.
//
// -------------------------------------------------------------
// Input file format  (default: testbench/vectors/input_vectors.hex)
//   - One test vector per line: a single packed 32-bit hex value
//     equal to {CH0, CH1, CH2, CH3} (8 bits each, MSB-first byte
//     order within the 32-bit value). With other parameters the
//     line holds NUM_CHANNELS*DATA_WIDTH bits, channel 0 first.
//       e.g. "a53cf05a" -> CH0=0xA5 CH1=0x3C CH2=0xF0 CH3=0x5A
//   - Blank lines and `//` / `/* */` comments are allowed - both
//     are already handled by $readmemh per the Verilog LRM.
//   - Up to MAX_VECTORS lines are read; raise the parameter below
//     if a larger input file is needed. The actual count does not
//     need to be hardcoded anywhere else - it is auto-detected at
//     run time (see "auto-detect vector count" below).
//
// Output files (default folder: golden_model/verification_logs/)
//   OUT_HEX     rtl_output_vectors.hex   - one line per input line, same
//               packed-32-bit-hex format, holding {CH0_OUT..CH3_OUT}
//               sampled after the vector has had time to fully settle.
//   OUT_STREAM  rtl_stream_vectors.txt   - one line per input line: the 32
//               bits seen on TDM_DATA during one full frame that starts at
//               bit_count==0 (first character = first bit on the wire).
//               This is what the Python golden model compares bit-by-bit.
//   OUT_LAT     rtl_latency_vectors.txt  - one integer per input line: clock
//               cycles from applying the vector until ALL FOUR outputs
//               equal it (-1 = never matched inside SETTLE_CYCLES). For
//               vector 0 it is counted from reset release (cold start).
//
// Every path can be overridden at run time with plusargs (no recompile,
// works in Icarus and in Vivado XSIM via -testplusarg):
//   +INPUT=<file> +OUT_HEX=<file> +OUT_STREAM=<file> +OUT_LAT=<file>
//
// PARAMETERS: NUM_CHANNELS and DATA_WIDTH (default 4 x 8) are passed to
// tdm_top. One input line is then one packed NUM_CHANNELS*DATA_WIDTH-bit
// vector {CH0, CH1, ...}, e.g. 4 x 16: "1234abcd00ff8001". Set them at the
// top of this file, with iverilog -P, or with Vivado -generic_top.
//
// ONE CASE FROM A TEXT FILE: CASE_FILE (parameter, or +CASE=<file>) reads
// one case written as NUM_CHANNELS = .., DATA_WIDTH = .., CH0 = .., CH1 = ..
// (see input/single_case.txt) instead of the vector list, and writes the
// trace below to TRACE_FILE (default rtl_result.txt).
//
// ONE CASE, BY EYE: TRACE_FILE (parameter, or +TRACE=<file>)
// set to a path other than "none" also writes, for the FIRST
// vector (cold start after reset), a cycle-by-cycle trace of one frame plus
// the receive latency: time, channel and bit on TDM_DATA, all outputs, and
// the cycle in which each output becomes valid. golden_model/single_case.py
// writes the expected trace in exactly the same format, so the two files
// can be opened side by side. +VCD=<file> dumps the waveform.
//
// SETTLE_CYCLES is deliberately a multiple of the frame length (32
// clocks for 4 x 8): this makes the sampling point land on the same
// bit_count phase every time regardless of which vector came
// before it, so results are reproducible run-to-run and
// simulator-to-simulator (see the header comment in tb_tdm_top.v
// for the background on why bit_count phase matters here).
//
// Run from the repository root:
//   iverilog -g2012 -o testbench/sim_filebased \
//       testbench/tb_tdm_top_filebased.v \
//       src/tdm_top.v src/tdm_counter.v src/tdm_mux.v \
//       src/tx_shift_reg.v src/rx_shift_reg.v src/tdm_demux.v
//   vvp testbench/sim_filebased
//
// IN VIVADO: this testbench only reaches $finish after every vector
// in the file has been processed, which can take longer than
// Vivado's default simulation runtime (often 1000 ns). If you just
// click "Run" (or the sim GUI's default runtime), it pauses partway
// through and the output file can look empty or truncated, because
// $fclose (which flushes everything to disk) hasn't executed yet.
// Use "Run All" (Tcl: run -all) so the simulation runs to $finish.
// Each line is also explicitly flushed with $fflush right after it
// is written, so even a partial/paused run shows whatever vectors
// have completed so far, not nothing.
// =============================================================
`timescale 1ns/1ps

module tb_tdm_top_filebased;

    parameter NUM_CHANNELS   = 4;
    parameter DATA_WIDTH     = 8;
    parameter MAX_VECTORS    = 256;
    parameter SETTLE_CYCLES  = 2 * NUM_CHANNELS * DATA_WIDTH;     // 2 frames (64 for 4 x 8)
    parameter SYNC_BIT_COUNT = (NUM_CHANNELS - 1) * DATA_WIDTH;   // start of the last channel slot (24)
    parameter CLK_PERIOD     = 10;

    localparam VW    = NUM_CHANNELS * DATA_WIDTH;   // bits per vector = bits per frame
    localparam FRAME = NUM_CHANNELS * DATA_WIDTH;   // clock cycles per frame
    
    parameter INPUT_FILE =
    "input/input_vectors.hex";
    parameter OUTPUT_FILE =
    "golden_model/verification_logs/rtl_output_vectors.hex";
    parameter STREAM_FILE =
    "golden_model/verification_logs/rtl_stream_vectors.txt";
    parameter LATENCY_FILE =
    "golden_model/verification_logs/rtl_latency_vectors.txt";
    parameter TRACE_FILE   = "none";   // set a path (or +TRACE=<file>) to write the one-case trace
    parameter CASE_FILE    = "none";   // set a path (or +CASE=<file>) to run ONE case from a text file

    // Effective paths (parameters above, optionally overridden by plusargs)
    reg [8*512-1:0] in_path, hex_path, stream_path, lat_path, trace_path, vcd_path, case_path;

    reg clk = 0;
    reg rst;
    reg  [VW-1:0] ch_in;     // {CH0, CH1, ..., CH(N-1)}, same packing as one input line
    wire [VW-1:0] ch_out;    // {CH0_OUT, CH1_OUT, ...}
    wire          TDM_DATA;

    always #(CLK_PERIOD/2) clk = ~clk;

    tdm_top #(.NUM_CHANNELS(NUM_CHANNELS), .DATA_WIDTH(DATA_WIDTH)) DUT (
        .clk      (clk),
        .rst      (rst),
        .ch_in    (ch_in),
        .TDM_DATA (TDM_DATA),
        .ch_out   (ch_out)
    );

    reg [VW-1:0] vectors [0:MAX_VECTORS-1];
    integer    num_vectors;
    integer    idx;
    integer    fd_out, fd_stream, fd_lat;
    reg        found_end;

    // one-frame TDM_DATA capture (same technique as tb_tdm_top.v PART 2)
    reg [FRAME-1:0] captured_stream;
    integer    k;

    // Latency measurement: free-running cycle counter on the falling edge
    // (so it never races with the posedge-driven DUT or the stimulus below)
    integer    cyc = 0;
    integer    t0;
    integer    lat_val;
    reg        watching = 1'b0;
    reg [VW-1:0] target;
    always @(negedge clk) begin
        cyc = cyc + 1;
        if (watching && (ch_out === target)) begin
            lat_val  = cyc - t0 - 1;   // clock edges after the change edge
            watching = 1'b0;
        end
    end

    reg [VW-1:0] expected, actual;
    integer    checks, errors;

    // ---------------------------------------------------------
    // Optional cycle-by-cycle trace of the first vector (+TRACE=<file>)
    // cycle 0 = first clock cycle after reset is released
    // ---------------------------------------------------------
    integer fd_tr, n, i;
    integer valid_cycle [0:NUM_CHANNELS-1];
    time    tr_t0, tr_edge;

    initial begin
        if ($value$plusargs("VCD=%s", vcd_path)) begin
            $dumpfile(vcd_path);
            $dumpvars(0, tb_tdm_top_filebased);
        end
        @(negedge rst);                             // trace_path is decided by the main block before reset
        if (trace_path != "none") begin
            tr_t0 = $time - 1;                      // reset is released 1 ns after the edge that starts cycle 0
            fd_tr = $fopen(trace_path, "w");
            $fdisplay(fd_tr, "# TDM single-case result");
            $fdisplay(fd_tr, "# source       : RTL simulation (tdm_top)");
            $fdisplay(fd_tr, "# NUM_CHANNELS : %0d", NUM_CHANNELS);
            $fdisplay(fd_tr, "# DATA_WIDTH   : %0d", DATA_WIDTH);
            $fdisplay(fd_tr, "# frame length : %0d cycles", FRAME);
            $fdisplay(fd_tr, "# clock period : %0d ns", CLK_PERIOD);
            $fdisplay(fd_tr, "# cycle 0      : first clock cycle after reset is released");
            $fdisplay(fd_tr, "#");
            $fdisplay(fd_tr, "# [1] inputs, one line per channel, and the packed vector {CH0, CH1, ...}");
            for (i = 0; i < NUM_CHANNELS; i = i + 1) begin
                $fdisplay(fd_tr, "CH%0d = %h", i, vectors[0][(NUM_CHANNELS-1-i)*DATA_WIDTH +: DATA_WIDTH]);
                valid_cycle[i] = -1;
            end
            $fdisplay(fd_tr, "vector = %h", vectors[0]);
            $fdisplay(fd_tr, "#");
            $fdisplay(fd_tr, "# [2] cycle-by-cycle trace: ch / bit = channel and bit number on TDM_DATA (MSB first)");
            $fdisplay(fd_tr, "# cycle  time_ns  ch  bit  TDM_DATA  | outputs during this cycle");
            for (n = 0; n < FRAME + 2; n = n + 1) begin
                @(negedge clk);
                tr_edge = $time - CLK_PERIOD/2;     // rising edge that started this cycle
                $fwrite(fd_tr, "%7d %8d %3d %4d %9d  |", n, tr_edge - tr_t0,
                        DUT.u_counter.channel_select, DATA_WIDTH - 1 - DUT.u_counter.bit_index, TDM_DATA);
                for (i = 0; i < NUM_CHANNELS; i = i + 1)
                    $fwrite(fd_tr, " CH%0d=%h", i, ch_out[(NUM_CHANNELS-1-i)*DATA_WIDTH +: DATA_WIDTH]);
                $fwrite(fd_tr, "\n");
                // word_done = 1 now -> the demux writes channel demux_select at the next
                // edge, so that output holds the new value from cycle n+1
                if (DUT.word_done === 1'b1 && valid_cycle[DUT.demux_select] < 0)
                    valid_cycle[DUT.demux_select] = n + 1;
            end
            $fdisplay(fd_tr, "#");
            $fdisplay(fd_tr, "# [3] output update: first cycle in which CHi_OUT holds the received value");
            for (i = 0; i < NUM_CHANNELS; i = i + 1)
                $fdisplay(fd_tr, "CH%0d_OUT = %h  from cycle %0d (%0d ns)", i,
                          ch_out[(NUM_CHANNELS-1-i)*DATA_WIDTH +: DATA_WIDTH],
                          valid_cycle[i], valid_cycle[i] * CLK_PERIOD);
            $fdisplay(fd_tr, "# cold-start latency: %0d cycles (%0d ns)",
                      valid_cycle[NUM_CHANNELS-1], valid_cycle[NUM_CHANNELS-1] * CLK_PERIOD);
            $fclose(fd_tr);
            $display("[filebased-tb] trace of vector #0 written: %0s", trace_path);
        end
    end

    // ---------------------------------------------------------
    // ONE CASE from a text file (CASE_FILE / +CASE=<file>):
    //     NUM_CHANNELS = 4
    //     DATA_WIDTH   = 8
    //     CH0 = a5          (hex, no 0x, one line per channel)
    //     CH1 = 3c   ...
    // NUM_CHANNELS and DATA_WIDTH come before the CH lines. Lines that match
    // none of these (e.g. // comments) are ignored.
    // NUM_CHANNELS / DATA_WIDTH must equal the parameters this testbench
    // was elaborated with (scripts/vivado_single_case.tcl and
    // scripts/run_single_case.py set them from the file automatically).
    // The channels are packed into vectors[0] = {CH0, CH1, ...}.
    // ---------------------------------------------------------
    // NUM_CHANNELS / DATA_WIDTH of the file must match the elaborated parameters
    task check_case_size;
        input integer file_n, file_w;
        begin
            if (file_n != NUM_CHANNELS || file_w != DATA_WIDTH) begin
                $display("[filebased-tb] ERROR: %0s asks for NUM_CHANNELS = %0d, DATA_WIDTH = %0d but this simulation was elaborated with %0d x %0d.",
                         case_path, file_n, file_w, NUM_CHANNELS, DATA_WIDTH);
                $display("[filebased-tb]        Write NUM_CHANNELS and DATA_WIDTH before the CH lines, and set the testbench parameters");
                $display("[filebased-tb]        to the same values (scripts/vivado_single_case.tcl and scripts/run_single_case.py do it for you).");
                $finish;
            end
        end
    endtask

    task read_case_file;
        integer fd_c, rc, v, ci, file_n, file_w;
        reg [8*512-1:0] line;
        reg [511:0]     hv;
        reg [1023:0]    seen;
        reg [VW-1:0]    case_vec;
        begin
            fd_c = $fopen(case_path, "r");
            if (fd_c == 0) begin
                $display("[filebased-tb] ERROR: cannot open case file %0s", case_path);
                $finish;
            end
            file_n = -1; file_w = -1; seen = 0; case_vec = {VW{1'b0}};
            while (!$feof(fd_c)) begin
                line = 0;
                rc = $fgets(line, fd_c);
                if (rc > 0) begin
                    if ($sscanf(line, " NUM_CHANNELS = %d", v) == 1)
                        file_n = v;
                    else if ($sscanf(line, " DATA_WIDTH = %d", v) == 1)
                        file_w = v;
                    else if ($sscanf(line, " CH%d = %h", ci, hv) == 2) begin
                        check_case_size(file_n, file_w);
                        if (ci < 0 || ci >= NUM_CHANNELS) begin
                            $display("[filebased-tb] ERROR: %0s: CH%0d does not exist (NUM_CHANNELS = %0d)",
                                     case_path, ci, NUM_CHANNELS);
                            $finish;
                        end
                        if ((hv >> DATA_WIDTH) != 0) begin
                            $display("[filebased-tb] ERROR: %0s: CH%0d = %0h is wider than DATA_WIDTH = %0d bits",
                                     case_path, ci, hv, DATA_WIDTH);
                            $finish;
                        end
                        case_vec[(NUM_CHANNELS-1-ci)*DATA_WIDTH +: DATA_WIDTH] = hv[DATA_WIDTH-1:0];
                        seen[ci] = 1'b1;
                    end
                end
            end
            $fclose(fd_c);
            check_case_size(file_n, file_w);
            for (ci = 0; ci < NUM_CHANNELS; ci = ci + 1)
                if (!seen[ci]) begin
                    $display("[filebased-tb] ERROR: %0s: line CH%0d = ... is missing", case_path, ci);
                    $finish;
                end
            vectors[0] = case_vec;
        end
    endtask

    initial begin
        // -----------------------------------------------------
        // 1) load vectors from the .hex file
        // -----------------------------------------------------
        in_path     = INPUT_FILE;
        hex_path    = OUTPUT_FILE;
        stream_path = STREAM_FILE;
        lat_path    = LATENCY_FILE;
        if ($value$plusargs("INPUT=%s",      in_path))     ;
        if ($value$plusargs("OUT_HEX=%s",    hex_path))    ;
        if ($value$plusargs("OUT_STREAM=%s", stream_path)) ;
        if ($value$plusargs("OUT_LAT=%s",    lat_path))    ;
        trace_path  = TRACE_FILE;
        case_path   = CASE_FILE;
        if ($value$plusargs("TRACE=%s",      trace_path))  ;
        if ($value$plusargs("CASE=%s",       case_path))   ;

        for (idx = 0; idx < MAX_VECTORS; idx = idx + 1)
            vectors[idx] = {VW{1'bx}};      // sentinel: "not filled by the file"

        if (case_path != "none") begin
            read_case_file;                                // ONE case: vectors[0] only
            if (trace_path == "none") trace_path = "rtl_result.txt";
            $display("[filebased-tb] case file %0s (%0d channels x %0d bits)",
                     case_path, NUM_CHANNELS, DATA_WIDTH);
        end
        else
            $readmemh(in_path, vectors);

        // auto-detect vector count: stop at the first still-unfilled
        // (all-X) entry, so the file's own length drives the loop -
        // nothing here needs to be hardcoded when the file changes.
        found_end   = 1'b0;
        num_vectors = MAX_VECTORS;
        for (idx = 0; idx < MAX_VECTORS; idx = idx + 1) begin
            if (!found_end && (^vectors[idx] === 1'bx)) begin
                found_end   = 1'b1;
                num_vectors = idx;
            end
        end

        if (num_vectors == 0) begin
            $display("[filebased-tb] ERROR: no vectors read from %0s (missing/empty file, or MAX_VECTORS too small)", in_path);
            $finish;
        end
        $display("[filebased-tb] loaded %0d test vector(s) from %0s", num_vectors,
                 (case_path != "none") ? case_path : in_path);

        // -----------------------------------------------------
        // 2) open the result file
        // -----------------------------------------------------
        fd_out    = $fopen(hex_path,    "w");
        fd_stream = $fopen(stream_path, "w");
        fd_lat    = $fopen(lat_path,    "w");
        if (fd_out == 0 || fd_stream == 0 || fd_lat == 0) begin
            $display("[filebased-tb] ERROR: cannot open an output file (%0s | %0s | %0s)",
                      hex_path, stream_path, lat_path);
            $finish;
        end

        // -----------------------------------------------------
        // 3) reset - with the #1 fix documented in tb_tdm_top.v's
        //    header (avoids a same-edge race between this block's
        //    "rst = 0" and the DUT's own posedge-clk reset sampling)
        //
        //    IMPORTANT: CH0..CH3 are preloaded with the FIRST vector
        //    (vectors[0]) *before* the reset-hold cycles, not with
        //    0. tx_shift_reg's cold-start fix (see src/tx_shift_reg.v)
        //    preloads tx_shift with mux_out on every clock while rst
        //    is held - so whatever CH0 happens to be during the last
        //    reset-held cycle is what gets latched as the very first
        //    byte on TDM_DATA. Holding CH0..CH3 at 0 during reset and
        //    only setting the real vector afterwards would silently
        //    reintroduce the old "CH1 comes out before CH0" cold-start
        //    bug that tx_shift_reg.v was specifically fixed to avoid.
        // -----------------------------------------------------
        rst = 1;
        ch_in = vectors[0];
        repeat (2) @(posedge clk);
        #1;
        rst = 0;
        // vector 0 latency = cold start, counted from reset release
        t0 = cyc; target = vectors[0]; lat_val = -1; watching = 1'b1;

        // -----------------------------------------------------
        // 4) drive every vector, one at a time: dump the settled
        //    output to the result file AND self-check it against
        //    the vector just fed in (expected == input, see the
        //    "SELF-CHECKING" note in the header)
        // -----------------------------------------------------
        checks = 0;
        errors = 0;
        for (idx = 0; idx < num_vectors; idx = idx + 1) begin
           if (idx > 0)
            while (DUT.u_counter.bit_count != SYNC_BIT_COUNT) @(posedge clk);
            ch_in = vectors[idx];
            if (idx > 0) begin
                t0 = cyc; target = vectors[idx]; lat_val = -1; watching = 1'b1;
            end
            repeat (SETTLE_CYCLES) @(posedge clk);

            actual   = ch_out;
            expected = vectors[idx];

            $fdisplay(fd_out, "%h", actual);
            $fflush(fd_out);   // visible on disk even if the run is paused before $finish
            $fdisplay(fd_lat, "%0d", lat_val);
            $fflush(fd_lat);

            // capture one full frame off the wire, starting exactly
            // at bit_count==0 (same pattern as tb_tdm_top.v PART 2); the
            // next iteration re-syncs to SYNC_BIT_COUNT before changing data
            while (DUT.u_counter.bit_count !== 0) @(posedge clk);
            captured_stream = {FRAME{1'b0}};
            for (k = 0; k < FRAME; k = k + 1) begin
                captured_stream = {captured_stream[FRAME-2:0], TDM_DATA};
                @(posedge clk);
            end
            $fdisplay(fd_stream, "%b", captured_stream);
            $fflush(fd_stream);

            checks = checks + 1;
            if (actual !== expected) begin
                errors = errors + 1;
                $display("[filebased-tb] [FAIL] vector #%0d : input=%h expected_out=%h actual_out=%h",
                          idx, vectors[idx], expected, actual);
            end else begin
                $display("[filebased-tb] [PASS] vector #%0d : %h", idx, actual);
            end
        end

        $fclose(fd_out);
        $fclose(fd_stream);
        $fclose(fd_lat);
        $display("======================================================");
        $display(" [filebased-tb] TONG KET: %0d vector, %0d loi", checks, errors);
        if (errors == 0) $display(" >>> TAT CA VECTOR PASSED (output khop input tung bit)");
        else              $display(" >>> CO %0d VECTOR FAILED - xem chi tiet [FAIL] phia tren", errors);
        $display(" ket qua chi tiet da ghi vao: %0s | %0s | %0s", hex_path, stream_path, lat_path);
        $display("======================================================");
        $finish;
    end

endmodule