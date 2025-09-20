// gate.sv (structural-ish “implementation”)

module counter2 (
    input  logic clk,
    input  logic rst_n,   // active-low reset
    input  logic en,
    output logic [1:0] q
);
    logic [1:0] internal_d;

    // When enabled, increment by 1 using bit tricks:
    //  - LSB toggles when en
    //  - MSB toggles when en AND carry from bit0 (i.e., q[0]==1)
    assign internal_d[0] = rst_n ? (en ? ~q[0]         : q[0])       : 1'b0;
    assign internal_d[1] = rst_n ? (en ? (q[1] ^ q[0]) : q[1])       : 1'b0;

    always_ff @(posedge clk) q <= internal_d;
endmodule
