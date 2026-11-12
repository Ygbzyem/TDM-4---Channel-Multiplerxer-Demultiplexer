// =============================================================
// Module      : tdm_top
// Function    : connects the five sub-modules and adds the timing
//               "glue" that compensates the one-clock delay of the
//               synchronous registers, so that no bit is lost, no
//               channel is shifted, and CH0 is the first channel to
//               appear after reset.
//
// Parameters  : NUM_CHANNELS (>= 2), DATA_WIDTH (>= 2).
//               Default 4 x 8 = the original design.
//               ch_in  = {CH0, CH1, ..., CH(N-1)}             (channel 0 = most significant word)
//               ch_out = {CH0_OUT, CH1_OUT, ..., CH(N-1)_OUT}  (same packing)
//               For 4 x 8 this is the packed 32-bit vector of the input files:
//               a53cf05a -> CH0=a5, CH1=3c, CH2=f0, CH3=5a.
//               Frame length = NUM_CHANNELS * DATA_WIDTH clock cycles.
//
// Glue logic (same three rules as the 4 x 8 design, written for any size):
//   1) mux_select  = channel of the NEXT clock cycle (look one step ahead),
//                    because tx_shift_reg loads on the clock edge that ends
//                    the current word.
//   2) load = word_boundary = (bit_index == DATA_WIDTH-1): load and latch at
//                    the END of a word, not at the start.
//   3) demux_select = channel_select delayed by one clock, because word_done
//                    is a registered pulse one clock after word_boundary.
// See docs/tdm_top.md for the explanation with a real trace.
// =============================================================
module tdm_top #(
    parameter NUM_CHANNELS = 4,
    parameter DATA_WIDTH   = 8
) (
    clk, rst, ch_in, TDM_DATA, ch_out
);
    function integer cnt_width;
        input integer value;
        integer v;
        begin
            v = value - 1;
            cnt_width = 0;
            while (v > 0) begin
                cnt_width = cnt_width + 1;
                v = v >> 1;
            end
            if (cnt_width == 0) cnt_width = 1;
        end
    endfunction

    localparam BIT_W   = cnt_width(DATA_WIDTH);
    localparam CH_W    = cnt_width(NUM_CHANNELS);
    localparam FRAME_W = cnt_width(NUM_CHANNELS * DATA_WIDTH);

    input  wire                               clk;
    input  wire                               rst;
    input  wire [NUM_CHANNELS*DATA_WIDTH-1:0] ch_in;
    output wire                               TDM_DATA;
    output wire [NUM_CHANNELS*DATA_WIDTH-1:0] ch_out;

    // -----------------------------------------------------------
    // The single time source
    // -----------------------------------------------------------
    wire [BIT_W-1:0]   bit_index;
    wire [CH_W-1:0]    channel_select;   // "live" value: used for the mux (via mux_select), NOT for the demux
    wire [FRAME_W-1:0] bit_count;        // not used here (testbench only), removed by synthesis

    tdm_counter #(.NUM_CHANNELS(NUM_CHANNELS), .DATA_WIDTH(DATA_WIDTH)) u_counter (
        .clk            (clk),
        .rst            (rst),
        .bit_index      (bit_index),
        .channel_select (channel_select),
        .bit_count      (bit_count)
    );

    // -----------------------------------------------------------
    // Glue logic
    // -----------------------------------------------------------
    wire last_bit = (bit_index == DATA_WIDTH - 1);              // last bit of the current word

    wire [CH_W-1:0] next_channel = (channel_select == NUM_CHANNELS - 1) ? {CH_W{1'b0}}
                                                                        : channel_select + 1'b1;
    wire [CH_W-1:0] mux_select   = last_bit ? next_channel : channel_select;   // rule 1: look ahead

    wire load          = last_bit;                               // rule 2: load at the end of a word
    wire word_boundary = last_bit;                               //         latch at the end of a word

    reg  [CH_W-1:0] demux_select;                                // rule 3: delayed copy
    always @(posedge clk) begin
        if (rst)
            demux_select <= {CH_W{1'b0}};
        else
            demux_select <= channel_select;
    end

    // -----------------------------------------------------------
    // Data path: mux -> tx_shift_reg -> TDM_DATA -> rx_shift_reg -> demux
    // -----------------------------------------------------------
    wire [DATA_WIDTH-1:0] mux_out;
    wire [DATA_WIDTH-1:0] rx_data;
    wire                  word_done;

    tdm_mux #(.NUM_CHANNELS(NUM_CHANNELS), .DATA_WIDTH(DATA_WIDTH)) u_mux (
        .ch_in          (ch_in),
        .channel_select (mux_select),
        .mux_out        (mux_out)
    );

    tx_shift_reg #(.DATA_WIDTH(DATA_WIDTH)) u_tx (
        .clk        (clk),
        .rst        (rst),
        .mux_out    (mux_out),
        .load       (load),
        .serial_out (TDM_DATA)
    );

    rx_shift_reg #(.DATA_WIDTH(DATA_WIDTH)) u_rx (
        .clk           (clk),
        .rst           (rst),
        .serial_data   (TDM_DATA),
        .word_boundary (word_boundary),
        .rx_data       (rx_data),
        .word_done     (word_done)
    );

    tdm_demux #(.NUM_CHANNELS(NUM_CHANNELS), .DATA_WIDTH(DATA_WIDTH)) u_demux (
        .clk            (clk),
        .rst            (rst),
        .rx_data        (rx_data),
        .channel_select (demux_select),   // delayed copy, NOT the live channel_select
        .word_done      (word_done),
        .ch_out         (ch_out)
    );

endmodule
