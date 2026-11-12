// =============================================================
// Module      : tdm_demux
// Function    : writes rx_data into the selected channel output when
//               word_done = 1; the other outputs keep their value.
//               ch_out = {CH0_OUT, CH1_OUT, ..., CH(N-1)_OUT}: channel 0
//               is the most significant word (same packing as ch_in).
// =============================================================
module tdm_demux #(
    parameter NUM_CHANNELS = 4,
    parameter DATA_WIDTH   = 8
) (
    clk, rst, rx_data, channel_select, word_done, ch_out
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

    input  wire                               clk;
    input  wire                               rst;
    input  wire [DATA_WIDTH-1:0]              rx_data;
    input  wire [CH_W-1:0]                    channel_select;
    input  wire                               word_done;
    output reg  [NUM_CHANNELS*DATA_WIDTH-1:0] ch_out;

    integer i;
    always @(posedge clk) begin
        if (rst)
            ch_out <= {NUM_CHANNELS*DATA_WIDTH{1'b0}};
        else if (word_done) begin
            for (i = 0; i < NUM_CHANNELS; i = i + 1)
                if (channel_select == i)
                    ch_out[(NUM_CHANNELS-1-i)*DATA_WIDTH +: DATA_WIDTH] <= rx_data;
        end
    end

endmodule
