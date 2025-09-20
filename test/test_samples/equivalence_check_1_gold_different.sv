// gold.sv (behavioral “spec”)

module counter2 (
    input  logic clk,
    input  logic rst_n,   // active-low reset
    input  logic en,
    output logic [1:0] q
);
    always_ff @(posedge clk) begin
        if (!rst_n)       q <= 2'b00;
        else if (en)      q <= q + 2'd0;
        else              q <= q;
    end
endmodule
