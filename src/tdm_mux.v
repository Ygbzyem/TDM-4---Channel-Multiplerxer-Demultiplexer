// =============================================================
// Module      : tdm_mux
// Function    : N-to-1 multiplexer, purely combinational.
//               ch_in = {CH0, CH1, ..., CH(N-1)}: channel 0 is the most
//               significant word, the same packing as the input vector
//               files (e.g. a53cf05a -> CH0=a5 ... CH3=5a).
// =============================================================
module tdm_mux #(
    parameter NUM_CHANNELS = 4,
    parameter DATA_WIDTH   = 8
) (
    ch_in, channel_select, mux_out
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

    localparam CH_W = cnt_width(NUM_CHANNELS);

    input  wire [NUM_CHANNELS*DATA_WIDTH-1:0] ch_in;
    input  wire [CH_W-1:0]                    channel_select;
    output reg  [DATA_WIDTH-1:0]              mux_out;

    integer i;
    always @(*) begin
        mux_out = {DATA_WIDTH{1'b0}};          // default value: no latch
        for (i = 0; i < NUM_CHANNELS; i = i + 1)
            if (channel_select == i)
                mux_out = ch_in[(NUM_CHANNELS-1-i)*DATA_WIDTH +: DATA_WIDTH];
    end
endmodule
