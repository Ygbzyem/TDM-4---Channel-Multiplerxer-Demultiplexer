`timescale 1ns/1ps

module tb_tdm_top;

    reg clk = 0;
    reg rst;
    reg [7:0] CH0, CH1, CH2, CH3;
    wire       TDM_DATA;
    wire [7:0] CH0_OUT, CH1_OUT, CH2_OUT, CH3_OUT;

    integer errors = 0;
    integer checks = 0;
    integer fp;

    always #5 clk = ~clk;

    // tdm_top is parameterized; this testbench checks the default 4 x 8 configuration.
    // The buses are packed {CH0, CH1, CH2, CH3} (channel 0 = most significant byte).
    tdm_top #(.NUM_CHANNELS(4), .DATA_WIDTH(8)) DUT (
        .clk      (clk),
        .rst      (rst),
        .ch_in    ({CH0, CH1, CH2, CH3}),
        .TDM_DATA (TDM_DATA),
        .ch_out   ({CH0_OUT, CH1_OUT, CH2_OUT, CH3_OUT})
    );

    task check_channel(input [7:0] expected, input [7:0] actual, input [255:0] label);
        begin
            checks = checks + 1;
            if (expected !== actual) begin
                $display("[FAIL] %0s : expected=%h actual=%h", label, expected, actual);
                errors = errors + 1;
            end else begin
                $display("[PASS] %0s : %h", label, actual);
            end
        end
    endtask

    // -----------------------------------------------------------
    // PHAN 2 helper: bat dung luc bit_count=0 roi lay mau 32 bit
    // tren TDM_DATA. Dung hierarchical reference (chi trong
    // testbench, khong tong hop) de doc bit_count noi bo cua
    // tdm_counter ben trong DUT, phuc vu dong bo lay mau - khong
    // anh huong RTL.
    // -----------------------------------------------------------
    reg [31:0] captured_frame;
    integer k;

    task capture_and_check_serial_frame(
    input [7:0] e0,
    input [7:0] e1,
    input [7:0] e2,
    input [7:0] e3,
    input [255:0] label
);

begin

    while (DUT.u_counter.bit_count !== 5'd0)
        @(posedge clk);

    captured_frame = 32'h0;

    for (k = 0; k < 32; k = k + 1) begin

        captured_frame = {
            captured_frame[30:0],
            TDM_DATA
        };

        $fwrite(fp, "%b", TDM_DATA);

        @(posedge clk);

    end

    $fwrite(fp, "\n");

    checks = checks + 1;

    if (captured_frame !== {e0,e1,e2,e3}) begin

        $display(
            "[FAIL] %0s : TDM_DATA=%h expected=%h",
            label,
            captured_frame,
            {e0,e1,e2,e3}
        );

        errors = errors + 1;

    end
    else begin

        $display(
            "[PASS] %0s : TDM_DATA=%h",
            label,
            captured_frame
        );

    end

end

endtask


    // -----------------------------------------------------------
    // PHAN 3 helper: 1 frame random, cho on dinh, kiem tra round-trip
    // -----------------------------------------------------------
    task run_random_frame(input integer frame_no);
        begin
            CH0 = $random; CH1 = $random; CH2 = $random; CH3 = $random;
            repeat (64) @(posedge clk);
            checks = checks + 1;
            if (CH0_OUT !== CH0 || CH1_OUT !== CH1 || CH2_OUT !== CH2 || CH3_OUT !== CH3) begin
                $display("[FAIL] RANDOM frame #%0d : in={%h,%h,%h,%h} out={%h,%h,%h,%h}",
                          frame_no, CH0, CH1, CH2, CH3, CH0_OUT, CH1_OUT, CH2_OUT, CH3_OUT);
                errors = errors + 1;
            end else begin
                $display("[PASS] RANDOM frame #%0d : {%h,%h,%h,%h}", frame_no, CH0, CH1, CH2, CH3);
            end
        end
    endtask

    integer f;

    initial begin
        $dumpfile("tb_tdm_top.vcd");
        $dumpvars(0, tb_tdm_top);
        fp = $fopen("rtl_output.txt", "w");

if (fp == 0) begin
    $display("ERROR: cannot open rtl_output.txt");
    $finish;
end

        // =========================================================
        // PHAN 1 - round-trip theo frame
        // =========================================================
        $display("======================================================");
        $display(" PHAN 1: round-trip CH_OUT theo tung frame");
        $display("======================================================");

        rst = 1;
        CH0 = 8'hA5; CH1 = 8'h3C; CH2 = 8'hF0; CH3 = 8'h5A;
        repeat (2) @(posedge clk);
        #1;                 // FIX: tranh race luc doi rst (xem comment dau file)
        rst = 0;

        repeat (64) @(posedge clk);
        check_channel(CH0, CH0_OUT, "WARM - CH0_OUT");
        check_channel(CH1, CH1_OUT, "WARM - CH1_OUT");
        check_channel(CH2, CH2_OUT, "WARM - CH2_OUT");
        check_channel(CH3, CH3_OUT, "WARM - CH3_OUT");

        CH0 = 8'h11; CH1 = 8'h22; CH2 = 8'h33; CH3 = 8'h44;
        repeat (64) @(posedge clk);
        check_channel(CH0, CH0_OUT, "F2 - CH0_OUT");
        check_channel(CH1, CH1_OUT, "F2 - CH1_OUT");
        check_channel(CH2, CH2_OUT, "F2 - CH2_OUT");
        check_channel(CH3, CH3_OUT, "F2 - CH3_OUT");

        CH0 = 8'h00; CH1 = 8'hFF; CH2 = 8'h01; CH3 = 8'h80;
        repeat (64) @(posedge clk);
        check_channel(CH0, CH0_OUT, "F3(bien) - CH0_OUT");
        check_channel(CH1, CH1_OUT, "F3(bien) - CH1_OUT");
        check_channel(CH2, CH2_OUT, "F3(bien) - CH2_OUT");
        check_channel(CH3, CH3_OUT, "F3(bien) - CH3_OUT");

        rst = 1;
        repeat (2) @(posedge clk);
        #1;                 // FIX: tranh race luc doi rst (xem comment dau file)
        rst = 0;
        CH0 = 8'h55; CH1 = 8'h66; CH2 = 8'h77; CH3 = 8'h88;
        repeat (64) @(posedge clk);
        check_channel(CH0, CH0_OUT, "sau reset giua chung - CH0_OUT");
        check_channel(CH1, CH1_OUT, "sau reset giua chung - CH1_OUT");
        check_channel(CH2, CH2_OUT, "sau reset giua chung - CH2_OUT");
        check_channel(CH3, CH3_OUT, "sau reset giua chung - CH3_OUT");

        // =========================================================
        // PHAN 2 - kiem tra tung bit tren TDM_DATA
        // =========================================================
        $display("======================================================");
        $display(" PHAN 2: kiem tra tung bit tren TDM_DATA (32 bit/frame)");
        $display("======================================================");

        CH0 = 8'hA5; CH1 = 8'h3C; CH2 = 8'hF0; CH3 = 8'h5A;
        repeat (64) @(posedge clk);  // giu on dinh >=2 frame truoc khi bat dau lay mau
        capture_and_check_serial_frame(CH0, CH1, CH2, CH3, "bit-check frame 1 (A5/3C/F0/5A)");

        CH0 = 8'h00; CH1 = 8'hFF; CH2 = 8'h81; CH3 = 8'h7E;
        repeat (64) @(posedge clk);
        capture_and_check_serial_frame(CH0, CH1, CH2, CH3, "bit-check frame 2 (bien: 00/FF/81/7E)");

        // =========================================================
        // PHAN 3 - random regression nhieu frame
        // =========================================================
        $display("======================================================");
        $display(" PHAN 3: random regression - 20 frame ngau nhien");
        $display("======================================================");

        for (f = 1; f <= 20; f = f + 1)
            run_random_frame(f);

        // =========================================================
        $display("======================================================");
        $display(" TONG KET: %0d check, %0d loi", checks, errors);
        if (errors == 0) $display(" >>> TAT CA TEST PASSED");
        else              $display(" >>> CO %0d TEST FAILED", errors);
        $display("======================================================");
        $fclose(fp);
        $finish;
    end

endmodule