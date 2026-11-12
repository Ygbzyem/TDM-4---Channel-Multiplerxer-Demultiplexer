// =============================================================
// Module      : tx_shift_reg
// Function    : parallel-in serial-out, MSB first.
//               Priority: reset, then load, then shift.
// =============================================================
module tx_shift_reg #(
    parameter DATA_WIDTH = 8
) (
    input  wire                  clk,
    input  wire                  rst,
    input  wire [DATA_WIDTH-1:0] mux_out,
    input  wire                  load,
    output wire                  serial_out
);

    reg [DATA_WIDTH-1:0] tx_shift;

    always @(posedge clk) begin
        if (rst)
            tx_shift <= mux_out;                                // preload CH0 so it is sent first
        else if (load)
            tx_shift <= mux_out;                                // LOAD: parallel load of the next word
        else
            tx_shift <= {tx_shift[DATA_WIDTH-2:0], 1'b0};       // SHIFT left, MSB goes out first
    end

    assign serial_out = tx_shift[DATA_WIDTH-1];

endmodule
