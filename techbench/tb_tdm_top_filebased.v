// =============================================================
// tb_tdm_top_filebased.v
//
// QUICK START (one case, Vivado or Icarus)
//   1. REPO_DIR below: leave "." when the simulation runs inside the
//      repository (Icarus from the repository folder, or a Vivado project
//      created inside it: the testbench looks up to 6 folders above the
//      run folder). Otherwise set the absolute path, forward slashes, e.g.
//      "C:/GitHub/TDM-4---Channel-Multiplerxer-Demultiplexer-".
//   2. Put the case in input/input_vectors.txt (copy one from
//      input/test_cases.txt) and set NUM_CHANNELS / DATA_WIDTH below to
//      the same values as in that file.
//   3. Run the simulation to the end (Vivado: Run All).
//      -> results/rtl_result.txt  (overwritten on every run)
//   4. python golden_model/golden_model.py
//      -> results/golden_result.txt (same format), then compare the two files.
//
// The rest of this header describes the second mode (RUN_CASE = 0): the
// automatic regression over a list of packed vectors used by
// golden_model/run_verification.py.
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
// ONE CASE (RUN_CASE = 1, the default): read REPO_DIR/input/input_vectors.txt
// (or +CASE=<file>), written as
//     NUM_CHANNELS = 4
//     DATA_WIDTH   = 8                  (bits per time slot)
//     CH0 = 0123456789abcdef            (the whole message of device 0, hex)
//     CH1 = deadbeef   ...              (messages may have different lengths)
// Each message is cut into DATA_WIDTH-bit slots. The testbench plays the
// devices: frame f carries slot f of every channel (CH0, CH1, ... in turn,
// then back to CH0 for the next slot), a channel whose message is finished
// sends 0, and the received slots are put back together per channel.
// The cycle-by-cycle trace and the received messages go to
// REPO_DIR/results/rtl_result.txt (or +TRACE=<file>). golden_model/golden_model.py
// writes the expected result of the same input file in exactly the same
// format to results/golden_result.txt. +VCD=<file> dumps the waveform.
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

    // ---- set these to match input/input_vectors.txt, and REPO_DIR once ----
    parameter NUM_CHANNELS   = 4;
    parameter DATA_WIDTH     = 8;
    parameter REPO_DIR       = ".";    // "." = find the repository automatically; or an absolute path, forward slashes
    parameter RUN_CASE       = 1;      // 1 = one case from input/input_vectors.txt, 0 = vector regression

    localparam CASE_FILE  = {REPO_DIR, "/input/input_vectors.txt"};
    localparam TRACE_FILE = {REPO_DIR, "/results/rtl_result.txt"};
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


    // Effective paths (parameters above, optionally overridden by plusargs)
    reg [8*512-1:0] in_path, hex_path, stream_path, lat_path, trace_path, vcd_path, case_path;

    reg clk = 0;
    reg rst;
    reg  [VW-1:0] ch_in;     // {CH0, CH1, ..., CH(N-1)}, same packing as one input line
    wire [VW-1:0] ch_out;    // {CH0_OUT, CH1_OUT, ...}
    wire          TDM_DATA;

    // The clock stops when the run is over (sim_done = 1). In the Vivado GUI a
    // short case can reach $finish inside the first 1000 ns of
    // launch_simulation; a following "run all" then returns at once instead
    // of running a free clock forever.
    reg sim_done = 1'b0;
    initial begin
        while (!sim_done) #(CLK_PERIOD/2) clk = ~clk;
    end

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

    initial begin
        if ($value$plusargs("VCD=%s", vcd_path)) begin
            $dumpfile(vcd_path);
            $dumpvars(0, tb_tdm_top_filebased);
        end
    end

    // =========================================================
    // ONE CASE FROM A TEXT FILE: messages cut into time slots
    // =========================================================
    parameter MAX_SLOTS = 256;                   // slots per channel
    localparam MAX_HEX  = 512;                   // hex digits per message

    reg [DATA_WIDTH-1:0] slot_mem [0:NUM_CHANNELS*MAX_SLOTS-1];   // slot s of channel c at c*MAX_SLOTS+s
    reg [DATA_WIDTH-1:0] rx_mem   [0:NUM_CHANNELS*MAX_SLOTS-1];   // received words, same layout
    integer              rx_cycle [0:NUM_CHANNELS*MAX_SLOTS-1];   // cycle in which the output took the word
    reg [8*MAX_HEX-1:0]  msg_str  [0:NUM_CHANNELS-1];             // message text, right-aligned
    integer              msg_len  [0:NUM_CHANNELS-1];             // hex digits
    integer              n_slots  [0:NUM_CHANNELS-1];
    integer              rx_count [0:NUM_CHANNELS-1];
    integer              n_frames;
    integer              fd_tr;

    // ---------------------------------------------------------
    // Waveform view, one scope per channel: CH[0], CH[1], ...
    // (Vivado: Scope window -> tb_tdm_top_filebased -> CH[0] ->
    //  select all objects -> Add to Wave Window)
    //   sent        slot the device presents now (= its slice of ch_in)
    //   received    word on the output now (= its slice of ch_out)
    //   expected    original slot from the input file that the output must
    //               hold now (0 after the message is finished)
    //   ok          1 while received == expected
    //   message_in  whole message of the device, as its slots side by side
    //   message_out slots received so far, side by side
    //   message_ok  1 once the whole message arrived unchanged
    // all_ok / all_messages_ok: the same for every channel at once.
    // Messages longer than MSG_VIEW_BITS show their last MSG_VIEW_BITS bits.
    // ---------------------------------------------------------
    parameter  MSG_VIEW_BITS = 128;
    reg  [VW-1:0]                       exp_out = {VW{1'b0}};
    reg  [NUM_CHANNELS*MSG_VIEW_BITS-1:0] msg_in_v  = 0;
    reg  [NUM_CHANNELS*MSG_VIEW_BITS-1:0] msg_out_v = 0;
    integer                             exp_cnt [0:NUM_CHANNELS-1];
    integer                             ec;
    wire [NUM_CHANNELS-1:0]             ok_v, msg_ok_v;
    wire all_ok          = &ok_v;
    wire all_messages_ok = &msg_ok_v;

    // demux writes ch_out on the clock edge after word_done: expected changes on the same edge
    always @(posedge clk) begin
        if (rst) begin
            for (ec = 0; ec < NUM_CHANNELS; ec = ec + 1) exp_cnt[ec] = 0;
            exp_out <= {VW{1'b0}};
        end else if (RUN_CASE && DUT.word_done === 1'b1) begin
            ec = DUT.demux_select;
            exp_out[(NUM_CHANNELS-1-ec)*DATA_WIDTH +: DATA_WIDTH] <=
                (exp_cnt[ec] < n_slots[ec]) ? slot_mem[ec*MAX_SLOTS + exp_cnt[ec]] : {DATA_WIDTH{1'b0}};
            exp_cnt[ec] = exp_cnt[ec] + 1;
        end
    end

    genvar gc;
    generate
        for (gc = 0; gc < NUM_CHANNELS; gc = gc + 1) begin : CH
            wire [DATA_WIDTH-1:0]    sent        = ch_in  [(NUM_CHANNELS-1-gc)*DATA_WIDTH +: DATA_WIDTH];
            wire [DATA_WIDTH-1:0]    received    = ch_out [(NUM_CHANNELS-1-gc)*DATA_WIDTH +: DATA_WIDTH];
            wire [DATA_WIDTH-1:0]    expected    = exp_out[(NUM_CHANNELS-1-gc)*DATA_WIDTH +: DATA_WIDTH];
            wire                     ok          = (received === expected);
            wire [MSG_VIEW_BITS-1:0] message_in  = msg_in_v [gc*MSG_VIEW_BITS +: MSG_VIEW_BITS];
            wire [MSG_VIEW_BITS-1:0] message_out = msg_out_v[gc*MSG_VIEW_BITS +: MSG_VIEW_BITS];
            wire                     message_ok  = (message_out === message_in);
            assign ok_v[gc]     = ok;
            assign msg_ok_v[gc] = message_ok;
        end
    endgenerate

    // ASCII hex digit -> {invalid, value}
    function [4:0] hex_nibble;
        input [7:0] c;
        begin
            if (c >= 8'h30 && c <= 8'h39)                       // 0..9
                hex_nibble = {1'b0, c[3:0]};
            else if ((c >= 8'h61 && c <= 8'h66) || (c >= 8'h41 && c <= 8'h46))   // a..f, A..F
                hex_nibble = {1'b0, c[3:0] + 4'd9};
            else
                hex_nibble = 5'h10;
        end
    endfunction

    // bit b (0 = MSB of the first hex digit) of the message of channel c
    function msg_bit;
        input integer c;
        input integer b;
        reg [4:0] nib;
        begin
            nib     = hex_nibble(msg_str[c][8*(msg_len[c] - 1 - b/4) +: 8]);
            msg_bit = nib[3 - (b % 4)];
        end
    endfunction

    // NUM_CHANNELS / DATA_WIDTH of the file must match the elaborated parameters
    task check_case_size;
        input integer file_n, file_w;
        begin
            if (file_n != NUM_CHANNELS || file_w != DATA_WIDTH) begin
                $display("[filebased-tb] ERROR: %0s asks for NUM_CHANNELS = %0d, DATA_WIDTH = %0d but this simulation was elaborated with %0d x %0d.",
                         case_path, file_n, file_w, NUM_CHANNELS, DATA_WIDTH);
                $display("[filebased-tb]        Write NUM_CHANNELS and DATA_WIDTH before the CH lines, and set the testbench parameters");
                $display("[filebased-tb]        to the same values at the top of this testbench.");
                stop_sim;
            end
        end
    endtask

    // End the run. Vivado (xsim) only ends at the end of the current time
    // step, so after $finish this process must wait instead of going on in
    // zero time (a loop reading a file that failed to open never ends).
    task stop_sim;
        begin
            sim_done = 1'b1;
            $finish;
            forever #(CLK_PERIOD);
        end
    endtask

    // REPO_DIR left at ".": look for input/input_vectors.txt in the current
    // folder and up to 6 folders above it. A Vivado project inside the
    // repository simulates in <project>/<project>.sim/sim_1/behav/xsim,
    // 5 folders below the repository. The files are opened here with
    // string literals (not with a path copied into a wide reg), which every
    // simulator accepts; read_message_case / run_message_case use these
    // descriptors. An absolute REPO_DIR is opened through the constant
    // CASE_FILE / TRACE_FILE in the same way (see the main initial block).
    integer case_fd_pre  = 0;
    integer trace_fd_pre = 0;
    task find_repo_dir;
        integer up, fd_t;
        begin
            fd_t = 0;
            for (up = 0; up <= 6 && fd_t == 0; up = up + 1) begin
                case (up)
                    0: begin
                        fd_t = $fopen("input/input_vectors.txt", "r");
                        if (fd_t != 0) begin
                            case_path = "input/input_vectors.txt";
                            trace_path = "results/rtl_result.txt";
                            trace_fd_pre = $fopen("results/rtl_result.txt", "w");
                        end
                    end
                    1: begin
                        fd_t = $fopen("../input/input_vectors.txt", "r");
                        if (fd_t != 0) begin
                            case_path = "../input/input_vectors.txt";
                            trace_path = "../results/rtl_result.txt";
                            trace_fd_pre = $fopen("../results/rtl_result.txt", "w");
                        end
                    end
                    2: begin
                        fd_t = $fopen("../../input/input_vectors.txt", "r");
                        if (fd_t != 0) begin
                            case_path = "../../input/input_vectors.txt";
                            trace_path = "../../results/rtl_result.txt";
                            trace_fd_pre = $fopen("../../results/rtl_result.txt", "w");
                        end
                    end
                    3: begin
                        fd_t = $fopen("../../../input/input_vectors.txt", "r");
                        if (fd_t != 0) begin
                            case_path = "../../../input/input_vectors.txt";
                            trace_path = "../../../results/rtl_result.txt";
                            trace_fd_pre = $fopen("../../../results/rtl_result.txt", "w");
                        end
                    end
                    4: begin
                        fd_t = $fopen("../../../../input/input_vectors.txt", "r");
                        if (fd_t != 0) begin
                            case_path = "../../../../input/input_vectors.txt";
                            trace_path = "../../../../results/rtl_result.txt";
                            trace_fd_pre = $fopen("../../../../results/rtl_result.txt", "w");
                        end
                    end
                    5: begin
                        fd_t = $fopen("../../../../../input/input_vectors.txt", "r");
                        if (fd_t != 0) begin
                            case_path = "../../../../../input/input_vectors.txt";
                            trace_path = "../../../../../results/rtl_result.txt";
                            trace_fd_pre = $fopen("../../../../../results/rtl_result.txt", "w");
                        end
                    end
                    default: begin
                        fd_t = $fopen("../../../../../../input/input_vectors.txt", "r");
                        if (fd_t != 0) begin
                            case_path = "../../../../../../input/input_vectors.txt";
                            trace_path = "../../../../../../results/rtl_result.txt";
                            trace_fd_pre = $fopen("../../../../../../results/rtl_result.txt", "w");
                        end
                    end
                endcase
            end
            case_fd_pre = fd_t;
        end
    endtask


    task case_error;
        input [8*200-1:0] msg;
        input integer     ch;
        begin
            $display("[filebased-tb] ERROR: %0s: CH%0d: %0s", case_path, ch, msg);
            stop_sim;
        end
    endtask

    // read the case file and cut every message into DATA_WIDTH-bit slots
    task read_message_case;
        integer fd_c, rc, v, ci, c, k, s, b, file_n, file_w, nbits;
        reg [8*1024-1:0]     line;
        reg [8*MAX_HEX-1:0]  tok;
        reg [1023:0]         seen;
        reg [DATA_WIDTH-1:0] word;
        begin
            fd_c = (case_fd_pre != 0) ? case_fd_pre : $fopen(case_path, "r");
            if (fd_c == 0) begin
                $display("[filebased-tb] ERROR: cannot open case file %0s", case_path);
                $display("[filebased-tb]        Set REPO_DIR at the top of this testbench to the repository folder (forward slashes),");
                $display("[filebased-tb]        e.g. \"C:/GitHub/TDM-4---Channel-Multiplerxer-Demultiplexer-\", and check that input/input_vectors.txt exists.");
                stop_sim;
            end
            file_n = -1; file_w = -1; seen = 0;
            while (!$feof(fd_c)) begin
                line = 0;
                rc = $fgets(line, fd_c);
                if (rc > 0) begin
                    tok = 0;
                    if ($sscanf(line, " NUM_CHANNELS = %d", v) == 1)
                        file_n = v;
                    else if ($sscanf(line, " DATA_WIDTH = %d", v) == 1)
                        file_w = v;
                    else if ($sscanf(line, " CH%d = %s", ci, tok) == 2) begin
                        check_case_size(file_n, file_w);
                        if (ci < 0 || ci >= NUM_CHANNELS) case_error("channel does not exist", ci);
                        msg_len[ci] = 0;
                        for (k = 0; k < MAX_HEX; k = k + 1)
                            if (tok[8*k +: 8] != 8'h00) msg_len[ci] = k + 1;
                        if (msg_len[ci] == 0) case_error("empty message", ci);
                        msg_str[ci] = tok;
                        for (k = 0; k < msg_len[ci]; k = k + 1)
                            if (hex_nibble(tok[8*k +: 8]) > 5'h0f) case_error("message must be hex digits only (no 0x)", ci);
                        seen[ci] = 1'b1;
                    end
                end
            end
            $fclose(fd_c);
            check_case_size(file_n, file_w);

            n_frames = 0;
            for (c = 0; c < NUM_CHANNELS; c = c + 1) begin
                if (!seen[c]) case_error("line is missing", c);
                nbits      = 4 * msg_len[c];
                n_slots[c] = (nbits + DATA_WIDTH - 1) / DATA_WIDTH;
                if (n_slots[c] > MAX_SLOTS) case_error("message longer than MAX_SLOTS slots", c);
                for (s = 0; s < n_slots[c]; s = s + 1) begin
                    for (b = 0; b < DATA_WIDTH; b = b + 1) begin
                        k = s * DATA_WIDTH + b;                    // message bit, MSB first
                        word[DATA_WIDTH-1-b] = (k < nbits) ? msg_bit(c, k) : 1'b0;   // last slot padded with 0
                    end
                    slot_mem[c*MAX_SLOTS + s] = word;
                end
                if (n_slots[c] > n_frames) n_frames = n_slots[c];
            end
        end
    endtask

    // put slot f of every channel on the inputs; a finished channel sends 0
    task apply_frame;
        input integer f;
        integer c;
        begin
            for (c = 0; c < NUM_CHANNELS; c = c + 1)
                ch_in[(NUM_CHANNELS-1-c)*DATA_WIDTH +: DATA_WIDTH] =
                    (f < n_slots[c]) ? slot_mem[c*MAX_SLOTS + f] : {DATA_WIDTH{1'b0}};
        end
    endtask

    // run the case, write the trace and the received messages, then stop
    task run_message_case;
        integer n, c, s, k, b, pend, last, errs;
        time    t_start, t_edge;
        reg [3:0] nib;
        begin
            read_message_case;
            fd_tr = (trace_fd_pre != 0) ? trace_fd_pre : $fopen(trace_path, "w");
            if (fd_tr == 0) begin
                $display("[filebased-tb] ERROR: cannot open %0s", trace_path);
                stop_sim;
            end
            last = n_frames * FRAME + 1;               // cycle in which the last word reaches its output

            $fdisplay(fd_tr, "# TDM case result");
            $fdisplay(fd_tr, "# source       : RTL simulation (tdm_top)");
            $fdisplay(fd_tr, "# NUM_CHANNELS : %0d", NUM_CHANNELS);
            $fdisplay(fd_tr, "# DATA_WIDTH   : %0d bits per slot", DATA_WIDTH);
            $fdisplay(fd_tr, "# frame length : %0d cycles (one slot of every channel)", FRAME);
            $fdisplay(fd_tr, "# frames       : %0d", n_frames);
            $fdisplay(fd_tr, "# clock period : %0d ns", CLK_PERIOD);
            $fdisplay(fd_tr, "# cycle 0      : first clock cycle after reset is released");
            $fdisplay(fd_tr, "#");
            $fdisplay(fd_tr, "# [1] messages and their slots (a finished channel sends 0)");
            for (c = 0; c < NUM_CHANNELS; c = c + 1) begin
                $fwrite(fd_tr, "CH%0d = ", c);
                for (k = msg_len[c] - 1; k >= 0; k = k - 1)
                    $fwrite(fd_tr, "%c", msg_str[c][8*k +: 8]);
                $fwrite(fd_tr, "  slots:");
                for (s = 0; s < n_slots[c]; s = s + 1)
                    $fwrite(fd_tr, " %h", slot_mem[c*MAX_SLOTS + s]);
                $fwrite(fd_tr, "\n");
            end
            $fdisplay(fd_tr, "#");
            $fdisplay(fd_tr, "# [2] cycle-by-cycle trace: ch / bit = channel and bit number on TDM_DATA (MSB first)");
            $fdisplay(fd_tr, "# cycle  time_ns  frame  ch  bit  TDM_DATA  | outputs during this cycle");

            for (c = 0; c < NUM_CHANNELS; c = c + 1) begin
                rx_count[c] = 0;
                msg_out_v[c*MSG_VIEW_BITS +: MSG_VIEW_BITS] = 0;               // waveform view
                msg_in_v [c*MSG_VIEW_BITS +: MSG_VIEW_BITS] = 0;
                for (s = 0; s < n_slots[c]; s = s + 1)
                    msg_in_v[c*MSG_VIEW_BITS +: MSG_VIEW_BITS] =
                        (msg_in_v[c*MSG_VIEW_BITS +: MSG_VIEW_BITS] << DATA_WIDTH) | slot_mem[c*MAX_SLOTS + s];
            end
            rst = 1'b1;
            apply_frame(0);                            // CH0 slot 0 is preloaded during reset
            repeat (2) @(posedge clk);
            t_start = $time;                           // rising edge that starts cycle 0
            #1 rst = 1'b0;

            pend = -1;
            for (n = 0; n <= last; n = n + 1) begin
                @(negedge clk);
                // the word announced by word_done in the previous cycle is on ch_out now
                if (pend >= 0) begin
                    rx_mem  [pend*MAX_SLOTS + rx_count[pend]] = ch_out[(NUM_CHANNELS-1-pend)*DATA_WIDTH +: DATA_WIDTH];
                    rx_cycle[pend*MAX_SLOTS + rx_count[pend]] = n;
                    if (rx_count[pend] < n_slots[pend])                          // waveform view
                        msg_out_v[pend*MSG_VIEW_BITS +: MSG_VIEW_BITS] =
                            (msg_out_v[pend*MSG_VIEW_BITS +: MSG_VIEW_BITS] << DATA_WIDTH)
                            | ch_out[(NUM_CHANNELS-1-pend)*DATA_WIDTH +: DATA_WIDTH];
                    rx_count[pend] = rx_count[pend] + 1;
                end
                pend = (DUT.word_done === 1'b1) ? DUT.demux_select : -1;

                t_edge = $time - CLK_PERIOD/2;         // rising edge that started this cycle
                $fwrite(fd_tr, "%7d %8d %6d %3d %4d %9d  |", n, t_edge - t_start, n / FRAME,
                        DUT.u_counter.channel_select, DATA_WIDTH - 1 - DUT.u_counter.bit_index, TDM_DATA);
                for (c = 0; c < NUM_CHANNELS; c = c + 1)
                    $fwrite(fd_tr, " CH%0d=%h", c, ch_out[(NUM_CHANNELS-1-c)*DATA_WIDTH +: DATA_WIDTH]);
                $fwrite(fd_tr, "\n");

                // the devices present their next slot in the last cycle of a frame,
                // before the clock edge on which CH0 of the next frame is loaded
                if (DUT.u_counter.channel_select == NUM_CHANNELS - 1 &&
                    DUT.u_counter.bit_index == DATA_WIDTH - 1)
                    apply_frame(n / FRAME + 1);        // after the last frame every channel sends 0
            end

            $fdisplay(fd_tr, "#");
            $fdisplay(fd_tr, "# [3] received slots per channel: value(cycle in which the output took it), rebuilt message");
            errs = 0;
            for (c = 0; c < NUM_CHANNELS; c = c + 1) begin
                $fwrite(fd_tr, "CH%0d_OUT :", c);
                for (s = 0; s < rx_count[c]; s = s + 1) begin
                    $fwrite(fd_tr, " %h(%0d)", rx_mem[c*MAX_SLOTS + s], rx_cycle[c*MAX_SLOTS + s]);
                    if (rx_mem[c*MAX_SLOTS + s] !== ((s < n_slots[c]) ? slot_mem[c*MAX_SLOTS + s] : {DATA_WIDTH{1'b0}}))
                        errs = errs + 1;
                end
                $fwrite(fd_tr, "\n");
                if (rx_count[c] != n_frames) errs = errs + 1;
            end
            for (c = 0; c < NUM_CHANNELS; c = c + 1) begin
                $fwrite(fd_tr, "CH%0d message = ", c);
                for (k = 0; k < msg_len[c]; k = k + 1) begin     // hex digit k = 4 received bits
                    for (b = 0; b < 4; b = b + 1)
                        nib[3-b] = rx_mem[c*MAX_SLOTS + (4*k + b) / DATA_WIDTH][DATA_WIDTH - 1 - (4*k + b) % DATA_WIDTH];
                    $fwrite(fd_tr, "%h", nib);
                end
                $fwrite(fd_tr, "\n");
            end
            $fdisplay(fd_tr, "# last output update: cycle %0d (%0d ns)", last, last * CLK_PERIOD);
            $fclose(fd_tr);

            $display("[filebased-tb] case %0s: %0d channels x %0d bits, %0d frames, trace written: %0s",
                     case_path, NUM_CHANNELS, DATA_WIDTH, n_frames, trace_path);
            if (errs == 0) $display("[filebased-tb] [PASS] every channel received its message");
            else           $display("[filebased-tb] [FAIL] %0d received slot(s) differ from the sent slots", errs);
            $display(" [filebased-tb] TONG KET: %0d kenh, %0d loi", NUM_CHANNELS, errs);
            stop_sim;
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
        if (RUN_CASE && REPO_DIR == "." && !$test$plusargs("CASE="))
            find_repo_dir;                                 // REPO_DIR not set: look for the repository
        if ($value$plusargs("TRACE=%s",      trace_path) && trace_fd_pre != 0) begin
            $fclose(trace_fd_pre);                         // +TRACE wins over the file found above
            trace_fd_pre = 0;
        end
        if ($value$plusargs("CASE=%s",       case_path))   ;
        if (RUN_CASE && case_fd_pre == 0 && REPO_DIR != "." && !$test$plusargs("CASE="))
            case_fd_pre = $fopen(CASE_FILE, "r");          // absolute REPO_DIR: open the constant path
        if (RUN_CASE && trace_fd_pre == 0 && REPO_DIR != "." && !$test$plusargs("TRACE="))
            trace_fd_pre = $fopen(TRACE_FILE, "w");
        if (RUN_CASE) $display("[filebased-tb] input file : %0s", case_path);

        for (idx = 0; idx < MAX_VECTORS; idx = idx + 1)
            vectors[idx] = {VW{1'bx}};      // sentinel: "not filled by the file"

        if (RUN_CASE)
            run_message_case;                              // ONE case from input/input_vectors.txt; ends with $finish

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
            stop_sim;
        end
        $display("[filebased-tb] loaded %0d test vector(s) from %0s", num_vectors, in_path);

        // -----------------------------------------------------
        // 2) open the result file
        // -----------------------------------------------------
        fd_out    = $fopen(hex_path,    "w");
        fd_stream = $fopen(stream_path, "w");
        fd_lat    = $fopen(lat_path,    "w");
        if (fd_out == 0 || fd_stream == 0 || fd_lat == 0) begin
            $display("[filebased-tb] ERROR: cannot open an output file (%0s | %0s | %0s)",
                      hex_path, stream_path, lat_path);
            stop_sim;
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
        stop_sim;
    end

endmodule