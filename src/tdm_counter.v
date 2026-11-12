// =============================================================
// Module      : tdm_counter
// Function    : the only time source of the system. Two cascaded
//               counters: bit_index counts the bit position inside
//               one channel word (0 .. DATA_WIDTH-1), channel_select
//               counts the channel slot (0 .. NUM_CHANNELS-1).
//               One frame = NUM_CHANNELS * DATA_WIDTH clock cycles.
//
// For the default 4 x 8 configuration {channel_select, bit_index}
// is exactly the old 5-bit bit_count, so the behaviour is unchanged.
// bit_count (position inside the frame) is kept as an output for the
// testbenches; it is not used by tdm_top, so synthesis removes it.
//
// Parameters  : NUM_CHANNELS >= 2, DATA_WIDTH >= 2
// =============================================================
module tdm_counter #(
    parameter NUM_CHANNELS = 4,
    parameter DATA_WIDTH   = 8
) (
    clk, rst, bit_index, channel_select, bit_count
);
    // bits needed to count 0 .. value-1 (at least 1); Verilog-2001 has no $clog2
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

    // ports are declared after the widths they depend on (Verilog-2001 safe)
    input  wire               clk;
    input  wire               rst;
    output reg  [BIT_W-1:0]   bit_index;        // bit position inside the word
    output reg  [CH_W-1:0]    channel_select;   // channel slot
    output wire [FRAME_W-1:0] bit_count;        // position inside the frame (testbench use)

    always @(posedge clk) begin
        if (rst) begin
            bit_index      <= {BIT_W{1'b0}};
            channel_select <= {CH_W{1'b0}};
        end
        else if (bit_index == DATA_WIDTH - 1) begin
            bit_index <= {BIT_W{1'b0}};                         // end of one word
            if (channel_select == NUM_CHANNELS - 1)
                channel_select <= {CH_W{1'b0}};                 // end of the frame
            else
                channel_select <= channel_select + 1'b1;
        end
        else begin
            bit_index <= bit_index + 1'b1;
        end
    end

    assign bit_count = channel_select * DATA_WIDTH + bit_index;

    // synthesis translate_off
    initial begin
        if (NUM_CHANNELS < 2 || DATA_WIDTH < 2) begin
            $display("ERROR: tdm_counter needs NUM_CHANNELS >= 2 and DATA_WIDTH >= 2");
            $finish;
        end
    end
    // synthesis translate_on
endmodule
