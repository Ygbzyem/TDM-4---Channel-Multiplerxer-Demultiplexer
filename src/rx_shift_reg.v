// =============================================================
// Module      : rx_shift_reg
// Function    : serial-in parallel-out, MSB first.
//               On word_boundary (last bit of a word) the complete
//               word is latched into rx_data and word_done pulses
//               for one clock.
// =============================================================
module rx_shift_reg #(
    parameter DATA_WIDTH = 8
) (
    input  wire                  clk,
    input  wire                  rst,
    input  wire                  serial_data,
    input  wire                  word_boundary,
    output reg  [DATA_WIDTH-1:0] rx_data,
    output reg                   word_done
);

    reg [DATA_WIDTH-1:0] rx_shift;

    always @(posedge clk) begin
        if (rst) begin
            rx_shift  <= {DATA_WIDTH{1'b0}};
            rx_data   <= {DATA_WIDTH{1'b0}};
            word_done <= 1'b0;
        end
        else begin
            word_done <= 1'b0;                                   // one-clock pulse

            rx_shift <= {rx_shift[DATA_WIDTH-2:0], serial_data}; // MSB-first shift

            if (word_boundary) begin
                // use the NEW value: old bits plus the bit on the wire now
                rx_data   <= {rx_shift[DATA_WIDTH-2:0], serial_data};
                word_done <= 1'b1;
            end
        end
    end

endmodule
