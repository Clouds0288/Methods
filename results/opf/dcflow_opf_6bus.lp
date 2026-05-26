\ Model dcflow_opf_6bus
\ LP format - for model browsing. Use MPS format to capture full model detail.
\ Signature: 0xfcfe7221cd9bf723
Minimize
  45 p_grid[0] + 45 p_grid[1] + 45 p_grid[2] + 45 p_grid[3] + 45 p_grid[4]
   + 45 p_grid[5] + 45 p_grid[6] + 70 p_grid[7] + 70 p_grid[8]
   + 70 p_grid[9] + 70 p_grid[10] + 70 p_grid[11] + 90 p_grid[12]
   + 90 p_grid[13] + 90 p_grid[14] + 90 p_grid[15] + 90 p_grid[16]
   + 120 p_grid[17] + 120 p_grid[18] + 120 p_grid[19] + 120 p_grid[20]
   + 75 p_grid[21] + 75 p_grid[22] + 75 p_grid[23] + 85 p_dg[0]
   + 85 p_dg[1] + 85 p_dg[2] + 85 p_dg[3] + 85 p_dg[4] + 85 p_dg[5]
   + 85 p_dg[6] + 85 p_dg[7] + 85 p_dg[8] + 85 p_dg[9] + 85 p_dg[10]
   + 85 p_dg[11] + 85 p_dg[12] + 85 p_dg[13] + 85 p_dg[14] + 85 p_dg[15]
   + 85 p_dg[16] + 85 p_dg[17] + 85 p_dg[18] + 85 p_dg[19] + 85 p_dg[20]
   + 85 p_dg[21] + 85 p_dg[22] + 85 p_dg[23]
Subject To
 slack_theta[0]: theta[1,0] = 0
 dc_flow[L12,0]: - 333.3333333333334 theta[1,0]
   + 333.3333333333334 theta[2,0] + P[L12,0] = 0
 branch_ub[L12,0]: P[L12,0] <= 6
 branch_lb[L12,0]: P[L12,0] >= -6
 dc_flow[L23,0]: - 400 theta[2,0] + 400 theta[3,0] + P[L23,0] = 0
 branch_ub[L23,0]: P[L23,0] <= 4.5
 branch_lb[L23,0]: P[L23,0] >= -4.5
 dc_flow[L34,0]: - 500 theta[3,0] + 500 theta[4,0] + P[L34,0] = 0
 branch_ub[L34,0]: P[L34,0] <= 4
 branch_lb[L34,0]: P[L34,0] >= -4
 dc_flow[L45,0]: - 454.5454545454546 theta[4,0]
   + 454.5454545454546 theta[5,0] + P[L45,0] = 0
 branch_ub[L45,0]: P[L45,0] <= 3.5
 branch_lb[L45,0]: P[L45,0] >= -3.5
 dc_flow[L56,0]: - 555.5555555555555 theta[5,0]
   + 555.5555555555555 theta[6,0] + P[L56,0] = 0
 branch_ub[L56,0]: P[L56,0] <= 3
 branch_lb[L56,0]: P[L56,0] >= -3
 p_balance[1,0]: - P[L12,0] + p_grid[0] = 0
 p_balance[2,0]: - P[L12,0] + P[L23,0] = -0.3825
 p_balance[3,0]: - P[L23,0] + P[L34,0] = -0.385
 p_balance[4,0]: - P[L34,0] + P[L45,0] = -0.525
 p_balance[5,0]: - P[L45,0] + P[L56,0] = -0.27
 p_balance[6,0]: P[L56,0] + p_dg[0] = 0.175
 slack_theta[1]: theta[1,1] = 0
 dc_flow[L12,1]: - 333.3333333333334 theta[1,1]
   + 333.3333333333334 theta[2,1] + P[L12,1] = 0
 branch_ub[L12,1]: P[L12,1] <= 6
 branch_lb[L12,1]: P[L12,1] >= -6
 dc_flow[L23,1]: - 400 theta[2,1] + 400 theta[3,1] + P[L23,1] = 0
 branch_ub[L23,1]: P[L23,1] <= 4.5
 branch_lb[L23,1]: P[L23,1] >= -4.5
 dc_flow[L34,1]: - 500 theta[3,1] + 500 theta[4,1] + P[L34,1] = 0
 branch_ub[L34,1]: P[L34,1] <= 4
 branch_lb[L34,1]: P[L34,1] >= -4
 dc_flow[L45,1]: - 454.5454545454546 theta[4,1]
   + 454.5454545454546 theta[5,1] + P[L45,1] = 0
 branch_ub[L45,1]: P[L45,1] <= 3.5
 branch_lb[L45,1]: P[L45,1] >= -3.5
 dc_flow[L56,1]: - 555.5555555555555 theta[5,1]
   + 555.5555555555555 theta[6,1] + P[L56,1] = 0
 branch_ub[L56,1]: P[L56,1] <= 3
 branch_lb[L56,1]: P[L56,1] >= -3
 p_balance[1,1]: - P[L12,1] + p_grid[1] = 0
 p_balance[2,1]: - P[L12,1] + P[L23,1] = -0.357
 p_balance[3,1]: - P[L23,1] + P[L34,1] = -0.363
 p_balance[4,1]: - P[L34,1] + P[L45,1] = -0.51
 p_balance[5,1]: - P[L45,1] + P[L56,1] = -0.252
 p_balance[6,1]: P[L56,1] + p_dg[1] = 0.165
 slack_theta[2]: theta[1,2] = 0
 dc_flow[L12,2]: - 333.3333333333334 theta[1,2]
   + 333.3333333333334 theta[2,2] + P[L12,2] = 0
 branch_ub[L12,2]: P[L12,2] <= 6
 branch_lb[L12,2]: P[L12,2] >= -6
 dc_flow[L23,2]: - 400 theta[2,2] + 400 theta[3,2] + P[L23,2] = 0
 branch_ub[L23,2]: P[L23,2] <= 4.5
 branch_lb[L23,2]: P[L23,2] >= -4.5
 dc_flow[L34,2]: - 500 theta[3,2] + 500 theta[4,2] + P[L34,2] = 0
 branch_ub[L34,2]: P[L34,2] <= 4
 branch_lb[L34,2]: P[L34,2] >= -4
 dc_flow[L45,2]: - 454.5454545454546 theta[4,2]
   + 454.5454545454546 theta[5,2] + P[L45,2] = 0
 branch_ub[L45,2]: P[L45,2] <= 3.5
 branch_lb[L45,2]: P[L45,2] >= -3.5
 dc_flow[L56,2]: - 555.5555555555555 theta[5,2]
   + 555.5555555555555 theta[6,2] + P[L56,2] = 0
 branch_ub[L56,2]: P[L56,2] <= 3
 branch_lb[L56,2]: P[L56,2] >= -3
 p_balance[1,2]: - P[L12,2] + p_grid[2] = 0
 p_balance[2,2]: - P[L12,2] + P[L23,2] = -0.34
 p_balance[3,2]: - P[L23,2] + P[L34,2] = -0.352
 p_balance[4,2]: - P[L34,2] + P[L45,2] = -0.495
 p_balance[5,2]: - P[L45,2] + P[L56,2] = -0.24
 p_balance[6,2]: P[L56,2] + p_dg[2] = 0.16
 slack_theta[3]: theta[1,3] = 0
 dc_flow[L12,3]: - 333.3333333333334 theta[1,3]
   + 333.3333333333334 theta[2,3] + P[L12,3] = 0
 branch_ub[L12,3]: P[L12,3] <= 6
 branch_lb[L12,3]: P[L12,3] >= -6
 dc_flow[L23,3]: - 400 theta[2,3] + 400 theta[3,3] + P[L23,3] = 0
 branch_ub[L23,3]: P[L23,3] <= 4.5
 branch_lb[L23,3]: P[L23,3] >= -4.5
 dc_flow[L34,3]: - 500 theta[3,3] + 500 theta[4,3] + P[L34,3] = 0
 branch_ub[L34,3]: P[L34,3] <= 4
 branch_lb[L34,3]: P[L34,3] >= -4
 dc_flow[L45,3]: - 454.5454545454546 theta[4,3]
   + 454.5454545454546 theta[5,3] + P[L45,3] = 0
 branch_ub[L45,3]: P[L45,3] <= 3.5
 branch_lb[L45,3]: P[L45,3] >= -3.5
 dc_flow[L56,3]: - 555.5555555555555 theta[5,3]
   + 555.5555555555555 theta[6,3] + P[L56,3] = 0
 branch_ub[L56,3]: P[L56,3] <= 3
 branch_lb[L56,3]: P[L56,3] >= -3
 p_balance[1,3]: - P[L12,3] + p_grid[3] = 0
 p_balance[2,3]: - P[L12,3] + P[L23,3] = -0.3315
 p_balance[3,3]: - P[L23,3] + P[L34,3] = -0.341
 p_balance[4,3]: - P[L34,3] + P[L45,3] = -0.4875
 p_balance[5,3]: - P[L45,3] + P[L56,3] = -0.234
 p_balance[6,3]: P[L56,3] + p_dg[3] = 0.155
 slack_theta[4]: theta[1,4] = 0
 dc_flow[L12,4]: - 333.3333333333334 theta[1,4]
   + 333.3333333333334 theta[2,4] + P[L12,4] = 0
 branch_ub[L12,4]: P[L12,4] <= 6
 branch_lb[L12,4]: P[L12,4] >= -6
 dc_flow[L23,4]: - 400 theta[2,4] + 400 theta[3,4] + P[L23,4] = 0
 branch_ub[L23,4]: P[L23,4] <= 4.5
 branch_lb[L23,4]: P[L23,4] >= -4.5
 dc_flow[L34,4]: - 500 theta[3,4] + 500 theta[4,4] + P[L34,4] = 0
 branch_ub[L34,4]: P[L34,4] <= 4
 branch_lb[L34,4]: P[L34,4] >= -4
 dc_flow[L45,4]: - 454.5454545454546 theta[4,4]
   + 454.5454545454546 theta[5,4] + P[L45,4] = 0
 branch_ub[L45,4]: P[L45,4] <= 3.5
 branch_lb[L45,4]: P[L45,4] >= -3.5
 dc_flow[L56,4]: - 555.5555555555555 theta[5,4]
   + 555.5555555555555 theta[6,4] + P[L56,4] = 0
 branch_ub[L56,4]: P[L56,4] <= 3
 branch_lb[L56,4]: P[L56,4] >= -3
 p_balance[1,4]: - P[L12,4] + p_grid[4] = 0
 p_balance[2,4]: - P[L12,4] + P[L23,4] = -0.34
 p_balance[3,4]: - P[L23,4] + P[L34,4] = -0.352
 p_balance[4,4]: - P[L34,4] + P[L45,4] = -0.495
 p_balance[5,4]: - P[L45,4] + P[L56,4] = -0.24
 p_balance[6,4]: P[L56,4] + p_dg[4] = 0.16
 slack_theta[5]: theta[1,5] = 0
 dc_flow[L12,5]: - 333.3333333333334 theta[1,5]
   + 333.3333333333334 theta[2,5] + P[L12,5] = 0
 branch_ub[L12,5]: P[L12,5] <= 6
 branch_lb[L12,5]: P[L12,5] >= -6
 dc_flow[L23,5]: - 400 theta[2,5] + 400 theta[3,5] + P[L23,5] = 0
 branch_ub[L23,5]: P[L23,5] <= 4.5
 branch_lb[L23,5]: P[L23,5] >= -4.5
 dc_flow[L34,5]: - 500 theta[3,5] + 500 theta[4,5] + P[L34,5] = 0
 branch_ub[L34,5]: P[L34,5] <= 4
 branch_lb[L34,5]: P[L34,5] >= -4
 dc_flow[L45,5]: - 454.5454545454546 theta[4,5]
   + 454.5454545454546 theta[5,5] + P[L45,5] = 0
 branch_ub[L45,5]: P[L45,5] <= 3.5
 branch_lb[L45,5]: P[L45,5] >= -3.5
 dc_flow[L56,5]: - 555.5555555555555 theta[5,5]
   + 555.5555555555555 theta[6,5] + P[L56,5] = 0
 branch_ub[L56,5]: P[L56,5] <= 3
 branch_lb[L56,5]: P[L56,5] >= -3
 p_balance[1,5]: - P[L12,5] + p_grid[5] = 0
 p_balance[2,5]: - P[L12,5] + P[L23,5] = -0.3995
 p_balance[3,5]: - P[L23,5] + P[L34,5] = -0.418
 p_balance[4,5]: - P[L34,5] + P[L45,5] = -0.54
 p_balance[5,5]: - P[L45,5] + P[L56,5] = -0.282
 p_balance[6,5]: P[L56,5] + p_dg[5] = 0.19
 slack_theta[6]: theta[1,6] = 0
 dc_flow[L12,6]: - 333.3333333333334 theta[1,6]
   + 333.3333333333334 theta[2,6] + P[L12,6] = 0
 branch_ub[L12,6]: P[L12,6] <= 6
 branch_lb[L12,6]: P[L12,6] >= -6
 dc_flow[L23,6]: - 400 theta[2,6] + 400 theta[3,6] + P[L23,6] = 0
 branch_ub[L23,6]: P[L23,6] <= 4.5
 branch_lb[L23,6]: P[L23,6] >= -4.5
 dc_flow[L34,6]: - 500 theta[3,6] + 500 theta[4,6] + P[L34,6] = 0
 branch_ub[L34,6]: P[L34,6] <= 4
 branch_lb[L34,6]: P[L34,6] >= -4
 dc_flow[L45,6]: - 454.5454545454546 theta[4,6]
   + 454.5454545454546 theta[5,6] + P[L45,6] = 0
 branch_ub[L45,6]: P[L45,6] <= 3.5
 branch_lb[L45,6]: P[L45,6] >= -3.5
 dc_flow[L56,6]: - 555.5555555555555 theta[5,6]
   + 555.5555555555555 theta[6,6] + P[L56,6] = 0
 branch_ub[L56,6]: P[L56,6] <= 3
 branch_lb[L56,6]: P[L56,6] >= -3
 p_balance[1,6]: - P[L12,6] + p_grid[6] = 0
 p_balance[2,6]: - P[L12,6] + P[L23,6] = -0.51
 p_balance[3,6]: - P[L23,6] + P[L34,6] = -0.605
 p_balance[4,6]: - P[L34,6] + P[L45,6] = -0.6
 p_balance[5,6]: - P[L45,6] + P[L56,6] = -0.36
 p_balance[6,6]: P[L56,6] + p_dg[6] = 0.275
 slack_theta[7]: theta[1,7] = 0
 dc_flow[L12,7]: - 333.3333333333334 theta[1,7]
   + 333.3333333333334 theta[2,7] + P[L12,7] = 0
 branch_ub[L12,7]: P[L12,7] <= 6
 branch_lb[L12,7]: P[L12,7] >= -6
 dc_flow[L23,7]: - 400 theta[2,7] + 400 theta[3,7] + P[L23,7] = 0
 branch_ub[L23,7]: P[L23,7] <= 4.5
 branch_lb[L23,7]: P[L23,7] >= -4.5
 dc_flow[L34,7]: - 500 theta[3,7] + 500 theta[4,7] + P[L34,7] = 0
 branch_ub[L34,7]: P[L34,7] <= 4
 branch_lb[L34,7]: P[L34,7] >= -4
 dc_flow[L45,7]: - 454.5454545454546 theta[4,7]
   + 454.5454545454546 theta[5,7] + P[L45,7] = 0
 branch_ub[L45,7]: P[L45,7] <= 3.5
 branch_lb[L45,7]: P[L45,7] >= -3.5
 dc_flow[L56,7]: - 555.5555555555555 theta[5,7]
   + 555.5555555555555 theta[6,7] + P[L56,7] = 0
 branch_ub[L56,7]: P[L56,7] <= 3
 branch_lb[L56,7]: P[L56,7] >= -3
 p_balance[1,7]: - P[L12,7] + p_grid[7] = 0
 p_balance[2,7]: - P[L12,7] + P[L23,7] = -0.612
 p_balance[3,7]: - P[L23,7] + P[L34,7] = -0.825
 p_balance[4,7]: - P[L34,7] + P[L45,7] = -0.66
 p_balance[5,7]: - P[L45,7] + P[L56,7] = -0.432
 p_balance[6,7]: P[L56,7] + p_dg[7] = 0.375
 slack_theta[8]: theta[1,8] = 0
 dc_flow[L12,8]: - 333.3333333333334 theta[1,8]
   + 333.3333333333334 theta[2,8] + P[L12,8] = 0
 branch_ub[L12,8]: P[L12,8] <= 6
 branch_lb[L12,8]: P[L12,8] >= -6
 dc_flow[L23,8]: - 400 theta[2,8] + 400 theta[3,8] + P[L23,8] = 0
 branch_ub[L23,8]: P[L23,8] <= 4.5
 branch_lb[L23,8]: P[L23,8] >= -4.5
 dc_flow[L34,8]: - 500 theta[3,8] + 500 theta[4,8] + P[L34,8] = 0
 branch_ub[L34,8]: P[L34,8] <= 4
 branch_lb[L34,8]: P[L34,8] >= -4
 dc_flow[L45,8]: - 454.5454545454546 theta[4,8]
   + 454.5454545454546 theta[5,8] + P[L45,8] = 0
 branch_ub[L45,8]: P[L45,8] <= 3.5
 branch_lb[L45,8]: P[L45,8] >= -3.5
 dc_flow[L56,8]: - 555.5555555555555 theta[5,8]
   + 555.5555555555555 theta[6,8] + P[L56,8] = 0
 branch_ub[L56,8]: P[L56,8] <= 3
 branch_lb[L56,8]: P[L56,8] >= -3
 p_balance[1,8]: - P[L12,8] + p_grid[8] = 0
 p_balance[2,8]: - P[L12,8] + P[L23,8] = -0.646
 p_balance[3,8]: - P[L23,8] + P[L34,8] = -0.99
 p_balance[4,8]: - P[L34,8] + P[L45,8] = -0.69
 p_balance[5,8]: - P[L45,8] + P[L56,8] = -0.456
 p_balance[6,8]: P[L56,8] + p_dg[8] = 0.45
 slack_theta[9]: theta[1,9] = 0
 dc_flow[L12,9]: - 333.3333333333334 theta[1,9]
   + 333.3333333333334 theta[2,9] + P[L12,9] = 0
 branch_ub[L12,9]: P[L12,9] <= 6
 branch_lb[L12,9]: P[L12,9] >= -6
 dc_flow[L23,9]: - 400 theta[2,9] + 400 theta[3,9] + P[L23,9] = 0
 branch_ub[L23,9]: P[L23,9] <= 4.5
 branch_lb[L23,9]: P[L23,9] >= -4.5
 dc_flow[L34,9]: - 500 theta[3,9] + 500 theta[4,9] + P[L34,9] = 0
 branch_ub[L34,9]: P[L34,9] <= 4
 branch_lb[L34,9]: P[L34,9] >= -4
 dc_flow[L45,9]: - 454.5454545454546 theta[4,9]
   + 454.5454545454546 theta[5,9] + P[L45,9] = 0
 branch_ub[L45,9]: P[L45,9] <= 3.5
 branch_lb[L45,9]: P[L45,9] >= -3.5
 dc_flow[L56,9]: - 555.5555555555555 theta[5,9]
   + 555.5555555555555 theta[6,9] + P[L56,9] = 0
 branch_ub[L56,9]: P[L56,9] <= 3
 branch_lb[L56,9]: P[L56,9] >= -3
 p_balance[1,9]: - P[L12,9] + p_grid[9] = 0
 p_balance[2,9]: - P[L12,9] + P[L23,9] = -0.595
 p_balance[3,9]: - P[L23,9] + P[L34,9] = -1.078
 p_balance[4,9]: - P[L34,9] + P[L45,9] = -0.7125
 p_balance[5,9]: - P[L45,9] + P[L56,9] = -0.42
 p_balance[6,9]: P[L56,9] + p_dg[9] = 0.49
 slack_theta[10]: theta[1,10] = 0
 dc_flow[L12,10]: - 333.3333333333334 theta[1,10]
   + 333.3333333333334 theta[2,10] + P[L12,10] = 0
 branch_ub[L12,10]: P[L12,10] <= 6
 branch_lb[L12,10]: P[L12,10] >= -6
 dc_flow[L23,10]: - 400 theta[2,10] + 400 theta[3,10] + P[L23,10] = 0
 branch_ub[L23,10]: P[L23,10] <= 4.5
 branch_lb[L23,10]: P[L23,10] >= -4.5
 dc_flow[L34,10]: - 500 theta[3,10] + 500 theta[4,10] + P[L34,10] = 0
 branch_ub[L34,10]: P[L34,10] <= 4
 branch_lb[L34,10]: P[L34,10] >= -4
 dc_flow[L45,10]: - 454.5454545454546 theta[4,10]
   + 454.5454545454546 theta[5,10] + P[L45,10] = 0
 branch_ub[L45,10]: P[L45,10] <= 3.5
 branch_lb[L45,10]: P[L45,10] >= -3.5
 dc_flow[L56,10]: - 555.5555555555555 theta[5,10]
   + 555.5555555555555 theta[6,10] + P[L56,10] = 0
 branch_ub[L56,10]: P[L56,10] <= 3
 branch_lb[L56,10]: P[L56,10] >= -3
 p_balance[1,10]: - P[L12,10] + p_grid[10] = 0
 p_balance[2,10]: - P[L12,10] + P[L23,10] = -0.561
 p_balance[3,10]: - P[L23,10] + P[L34,10] = -1.1
 p_balance[4,10]: - P[L34,10] + P[L45,10] = -0.72
 p_balance[5,10]: - P[L45,10] + P[L56,10] = -0.396
 p_balance[6,10]: P[L56,10] + p_dg[10] = 0.5
 slack_theta[11]: theta[1,11] = 0
 dc_flow[L12,11]: - 333.3333333333334 theta[1,11]
   + 333.3333333333334 theta[2,11] + P[L12,11] = 0
 branch_ub[L12,11]: P[L12,11] <= 6
 branch_lb[L12,11]: P[L12,11] >= -6
 dc_flow[L23,11]: - 400 theta[2,11] + 400 theta[3,11] + P[L23,11] = 0
 branch_ub[L23,11]: P[L23,11] <= 4.5
 branch_lb[L23,11]: P[L23,11] >= -4.5
 dc_flow[L34,11]: - 500 theta[3,11] + 500 theta[4,11] + P[L34,11] = 0
 branch_ub[L34,11]: P[L34,11] <= 4
 branch_lb[L34,11]: P[L34,11] >= -4
 dc_flow[L45,11]: - 454.5454545454546 theta[4,11]
   + 454.5454545454546 theta[5,11] + P[L45,11] = 0
 branch_ub[L45,11]: P[L45,11] <= 3.5
 branch_lb[L45,11]: P[L45,11] >= -3.5
 dc_flow[L56,11]: - 555.5555555555555 theta[5,11]
   + 555.5555555555555 theta[6,11] + P[L56,11] = 0
 branch_ub[L56,11]: P[L56,11] <= 3
 branch_lb[L56,11]: P[L56,11] >= -3
 p_balance[1,11]: - P[L12,11] + p_grid[11] = 0
 p_balance[2,11]: - P[L12,11] + P[L23,11] = -0.544
 p_balance[3,11]: - P[L23,11] + P[L34,11] = -1.078
 p_balance[4,11]: - P[L34,11] + P[L45,11] = -0.7275
 p_balance[5,11]: - P[L45,11] + P[L56,11] = -0.384
 p_balance[6,11]: P[L56,11] + p_dg[11] = 0.49
 slack_theta[12]: theta[1,12] = 0
 dc_flow[L12,12]: - 333.3333333333334 theta[1,12]
   + 333.3333333333334 theta[2,12] + P[L12,12] = 0
 branch_ub[L12,12]: P[L12,12] <= 6
 branch_lb[L12,12]: P[L12,12] >= -6
 dc_flow[L23,12]: - 400 theta[2,12] + 400 theta[3,12] + P[L23,12] = 0
 branch_ub[L23,12]: P[L23,12] <= 4.5
 branch_lb[L23,12]: P[L23,12] >= -4.5
 dc_flow[L34,12]: - 500 theta[3,12] + 500 theta[4,12] + P[L34,12] = 0
 branch_ub[L34,12]: P[L34,12] <= 4
 branch_lb[L34,12]: P[L34,12] >= -4
 dc_flow[L45,12]: - 454.5454545454546 theta[4,12]
   + 454.5454545454546 theta[5,12] + P[L45,12] = 0
 branch_ub[L45,12]: P[L45,12] <= 3.5
 branch_lb[L45,12]: P[L45,12] >= -3.5
 dc_flow[L56,12]: - 555.5555555555555 theta[5,12]
   + 555.5555555555555 theta[6,12] + P[L56,12] = 0
 branch_ub[L56,12]: P[L56,12] <= 3
 branch_lb[L56,12]: P[L56,12] >= -3
 p_balance[1,12]: - P[L12,12] + p_grid[12] = 0
 p_balance[2,12]: - P[L12,12] + P[L23,12] = -0.527
 p_balance[3,12]: - P[L23,12] + P[L34,12] = -1.045
 p_balance[4,12]: - P[L34,12] + P[L45,12] = -0.72
 p_balance[5,12]: - P[L45,12] + P[L56,12] = -0.372
 p_balance[6,12]: P[L56,12] + p_dg[12] = 0.475
 slack_theta[13]: theta[1,13] = 0
 dc_flow[L12,13]: - 333.3333333333334 theta[1,13]
   + 333.3333333333334 theta[2,13] + P[L12,13] = 0
 branch_ub[L12,13]: P[L12,13] <= 6
 branch_lb[L12,13]: P[L12,13] >= -6
 dc_flow[L23,13]: - 400 theta[2,13] + 400 theta[3,13] + P[L23,13] = 0
 branch_ub[L23,13]: P[L23,13] <= 4.5
 branch_lb[L23,13]: P[L23,13] >= -4.5
 dc_flow[L34,13]: - 500 theta[3,13] + 500 theta[4,13] + P[L34,13] = 0
 branch_ub[L34,13]: P[L34,13] <= 4
 branch_lb[L34,13]: P[L34,13] >= -4
 dc_flow[L45,13]: - 454.5454545454546 theta[4,13]
   + 454.5454545454546 theta[5,13] + P[L45,13] = 0
 branch_ub[L45,13]: P[L45,13] <= 3.5
 branch_lb[L45,13]: P[L45,13] >= -3.5
 dc_flow[L56,13]: - 555.5555555555555 theta[5,13]
   + 555.5555555555555 theta[6,13] + P[L56,13] = 0
 branch_ub[L56,13]: P[L56,13] <= 3
 branch_lb[L56,13]: P[L56,13] >= -3
 p_balance[1,13]: - P[L12,13] + p_grid[13] = 0
 p_balance[2,13]: - P[L12,13] + P[L23,13] = -0.5185
 p_balance[3,13]: - P[L23,13] + P[L34,13] = -1.034
 p_balance[4,13]: - P[L34,13] + P[L45,13] = -0.72
 p_balance[5,13]: - P[L45,13] + P[L56,13] = -0.366
 p_balance[6,13]: P[L56,13] + p_dg[13] = 0.47
 slack_theta[14]: theta[1,14] = 0
 dc_flow[L12,14]: - 333.3333333333334 theta[1,14]
   + 333.3333333333334 theta[2,14] + P[L12,14] = 0
 branch_ub[L12,14]: P[L12,14] <= 6
 branch_lb[L12,14]: P[L12,14] >= -6
 dc_flow[L23,14]: - 400 theta[2,14] + 400 theta[3,14] + P[L23,14] = 0
 branch_ub[L23,14]: P[L23,14] <= 4.5
 branch_lb[L23,14]: P[L23,14] >= -4.5
 dc_flow[L34,14]: - 500 theta[3,14] + 500 theta[4,14] + P[L34,14] = 0
 branch_ub[L34,14]: P[L34,14] <= 4
 branch_lb[L34,14]: P[L34,14] >= -4
 dc_flow[L45,14]: - 454.5454545454546 theta[4,14]
   + 454.5454545454546 theta[5,14] + P[L45,14] = 0
 branch_ub[L45,14]: P[L45,14] <= 3.5
 branch_lb[L45,14]: P[L45,14] >= -3.5
 dc_flow[L56,14]: - 555.5555555555555 theta[5,14]
   + 555.5555555555555 theta[6,14] + P[L56,14] = 0
 branch_ub[L56,14]: P[L56,14] <= 3
 branch_lb[L56,14]: P[L56,14] >= -3
 p_balance[1,14]: - P[L12,14] + p_grid[14] = 0
 p_balance[2,14]: - P[L12,14] + P[L23,14] = -0.5355
 p_balance[3,14]: - P[L23,14] + P[L34,14] = -1.023
 p_balance[4,14]: - P[L34,14] + P[L45,14] = -0.7125
 p_balance[5,14]: - P[L45,14] + P[L56,14] = -0.378
 p_balance[6,14]: P[L56,14] + p_dg[14] = 0.465
 slack_theta[15]: theta[1,15] = 0
 dc_flow[L12,15]: - 333.3333333333334 theta[1,15]
   + 333.3333333333334 theta[2,15] + P[L12,15] = 0
 branch_ub[L12,15]: P[L12,15] <= 6
 branch_lb[L12,15]: P[L12,15] >= -6
 dc_flow[L23,15]: - 400 theta[2,15] + 400 theta[3,15] + P[L23,15] = 0
 branch_ub[L23,15]: P[L23,15] <= 4.5
 branch_lb[L23,15]: P[L23,15] >= -4.5
 dc_flow[L34,15]: - 500 theta[3,15] + 500 theta[4,15] + P[L34,15] = 0
 branch_ub[L34,15]: P[L34,15] <= 4
 branch_lb[L34,15]: P[L34,15] >= -4
 dc_flow[L45,15]: - 454.5454545454546 theta[4,15]
   + 454.5454545454546 theta[5,15] + P[L45,15] = 0
 branch_ub[L45,15]: P[L45,15] <= 3.5
 branch_lb[L45,15]: P[L45,15] >= -3.5
 dc_flow[L56,15]: - 555.5555555555555 theta[5,15]
   + 555.5555555555555 theta[6,15] + P[L56,15] = 0
 branch_ub[L56,15]: P[L56,15] <= 3
 branch_lb[L56,15]: P[L56,15] >= -3
 p_balance[1,15]: - P[L12,15] + p_grid[15] = 0
 p_balance[2,15]: - P[L12,15] + P[L23,15] = -0.5865
 p_balance[3,15]: - P[L23,15] + P[L34,15] = -0.99
 p_balance[4,15]: - P[L34,15] + P[L45,15] = -0.7125
 p_balance[5,15]: - P[L45,15] + P[L56,15] = -0.414
 p_balance[6,15]: P[L56,15] + p_dg[15] = 0.45
 slack_theta[16]: theta[1,16] = 0
 dc_flow[L12,16]: - 333.3333333333334 theta[1,16]
   + 333.3333333333334 theta[2,16] + P[L12,16] = 0
 branch_ub[L12,16]: P[L12,16] <= 6
 branch_lb[L12,16]: P[L12,16] >= -6
 dc_flow[L23,16]: - 400 theta[2,16] + 400 theta[3,16] + P[L23,16] = 0
 branch_ub[L23,16]: P[L23,16] <= 4.5
 branch_lb[L23,16]: P[L23,16] >= -4.5
 dc_flow[L34,16]: - 500 theta[3,16] + 500 theta[4,16] + P[L34,16] = 0
 branch_ub[L34,16]: P[L34,16] <= 4
 branch_lb[L34,16]: P[L34,16] >= -4
 dc_flow[L45,16]: - 454.5454545454546 theta[4,16]
   + 454.5454545454546 theta[5,16] + P[L45,16] = 0
 branch_ub[L45,16]: P[L45,16] <= 3.5
 branch_lb[L45,16]: P[L45,16] >= -3.5
 dc_flow[L56,16]: - 555.5555555555555 theta[5,16]
   + 555.5555555555555 theta[6,16] + P[L56,16] = 0
 branch_ub[L56,16]: P[L56,16] <= 3
 branch_lb[L56,16]: P[L56,16] >= -3
 p_balance[1,16]: - P[L12,16] + p_grid[16] = 0
 p_balance[2,16]: - P[L12,16] + P[L23,16] = -0.68
 p_balance[3,16]: - P[L23,16] + P[L34,16] = -0.902
 p_balance[4,16]: - P[L34,16] + P[L45,16] = -0.705
 p_balance[5,16]: - P[L45,16] + P[L56,16] = -0.48
 p_balance[6,16]: P[L56,16] + p_dg[16] = 0.41
 slack_theta[17]: theta[1,17] = 0
 dc_flow[L12,17]: - 333.3333333333334 theta[1,17]
   + 333.3333333333334 theta[2,17] + P[L12,17] = 0
 branch_ub[L12,17]: P[L12,17] <= 6
 branch_lb[L12,17]: P[L12,17] >= -6
 dc_flow[L23,17]: - 400 theta[2,17] + 400 theta[3,17] + P[L23,17] = 0
 branch_ub[L23,17]: P[L23,17] <= 4.5
 branch_lb[L23,17]: P[L23,17] >= -4.5
 dc_flow[L34,17]: - 500 theta[3,17] + 500 theta[4,17] + P[L34,17] = 0
 branch_ub[L34,17]: P[L34,17] <= 4
 branch_lb[L34,17]: P[L34,17] >= -4
 dc_flow[L45,17]: - 454.5454545454546 theta[4,17]
   + 454.5454545454546 theta[5,17] + P[L45,17] = 0
 branch_ub[L45,17]: P[L45,17] <= 3.5
 branch_lb[L45,17]: P[L45,17] >= -3.5
 dc_flow[L56,17]: - 555.5555555555555 theta[5,17]
   + 555.5555555555555 theta[6,17] + P[L56,17] = 0
 branch_ub[L56,17]: P[L56,17] <= 3
 branch_lb[L56,17]: P[L56,17] >= -3
 p_balance[1,17]: - P[L12,17] + p_grid[17] = 0
 p_balance[2,17]: - P[L12,17] + P[L23,17] = -0.8075
 p_balance[3,17]: - P[L23,17] + P[L34,17] = -0.77
 p_balance[4,17]: - P[L34,17] + P[L45,17] = -0.675
 p_balance[5,17]: - P[L45,17] + P[L56,17] = -0.57
 p_balance[6,17]: P[L56,17] + p_dg[17] = 0.35
 slack_theta[18]: theta[1,18] = 0
 dc_flow[L12,18]: - 333.3333333333334 theta[1,18]
   + 333.3333333333334 theta[2,18] + P[L12,18] = 0
 branch_ub[L12,18]: P[L12,18] <= 6
 branch_lb[L12,18]: P[L12,18] >= -6
 dc_flow[L23,18]: - 400 theta[2,18] + 400 theta[3,18] + P[L23,18] = 0
 branch_ub[L23,18]: P[L23,18] <= 4.5
 branch_lb[L23,18]: P[L23,18] >= -4.5
 dc_flow[L34,18]: - 500 theta[3,18] + 500 theta[4,18] + P[L34,18] = 0
 branch_ub[L34,18]: P[L34,18] <= 4
 branch_lb[L34,18]: P[L34,18] >= -4
 dc_flow[L45,18]: - 454.5454545454546 theta[4,18]
   + 454.5454545454546 theta[5,18] + P[L45,18] = 0
 branch_ub[L45,18]: P[L45,18] <= 3.5
 branch_lb[L45,18]: P[L45,18] >= -3.5
 dc_flow[L56,18]: - 555.5555555555555 theta[5,18]
   + 555.5555555555555 theta[6,18] + P[L56,18] = 0
 branch_ub[L56,18]: P[L56,18] <= 3
 branch_lb[L56,18]: P[L56,18] >= -3
 p_balance[1,18]: - P[L12,18] + p_grid[18] = 0
 p_balance[2,18]: - P[L12,18] + P[L23,18] = -0.85
 p_balance[3,18]: - P[L23,18] + P[L34,18] = -0.66
 p_balance[4,18]: - P[L34,18] + P[L45,18] = -0.645
 p_balance[5,18]: - P[L45,18] + P[L56,18] = -0.6
 p_balance[6,18]: P[L56,18] + p_dg[18] = 0.3
 slack_theta[19]: theta[1,19] = 0
 dc_flow[L12,19]: - 333.3333333333334 theta[1,19]
   + 333.3333333333334 theta[2,19] + P[L12,19] = 0
 branch_ub[L12,19]: P[L12,19] <= 6
 branch_lb[L12,19]: P[L12,19] >= -6
 dc_flow[L23,19]: - 400 theta[2,19] + 400 theta[3,19] + P[L23,19] = 0
 branch_ub[L23,19]: P[L23,19] <= 4.5
 branch_lb[L23,19]: P[L23,19] >= -4.5
 dc_flow[L34,19]: - 500 theta[3,19] + 500 theta[4,19] + P[L34,19] = 0
 branch_ub[L34,19]: P[L34,19] <= 4
 branch_lb[L34,19]: P[L34,19] >= -4
 dc_flow[L45,19]: - 454.5454545454546 theta[4,19]
   + 454.5454545454546 theta[5,19] + P[L45,19] = 0
 branch_ub[L45,19]: P[L45,19] <= 3.5
 branch_lb[L45,19]: P[L45,19] >= -3.5
 dc_flow[L56,19]: - 555.5555555555555 theta[5,19]
   + 555.5555555555555 theta[6,19] + P[L56,19] = 0
 branch_ub[L56,19]: P[L56,19] <= 3
 branch_lb[L56,19]: P[L56,19] >= -3
 p_balance[1,19]: - P[L12,19] + p_grid[19] = 0
 p_balance[2,19]: - P[L12,19] + P[L23,19] = -0.816
 p_balance[3,19]: - P[L23,19] + P[L34,19] = -0.572
 p_balance[4,19]: - P[L34,19] + P[L45,19] = -0.615
 p_balance[5,19]: - P[L45,19] + P[L56,19] = -0.576
 p_balance[6,19]: P[L56,19] + p_dg[19] = 0.26
 slack_theta[20]: theta[1,20] = 0
 dc_flow[L12,20]: - 333.3333333333334 theta[1,20]
   + 333.3333333333334 theta[2,20] + P[L12,20] = 0
 branch_ub[L12,20]: P[L12,20] <= 6
 branch_lb[L12,20]: P[L12,20] >= -6
 dc_flow[L23,20]: - 400 theta[2,20] + 400 theta[3,20] + P[L23,20] = 0
 branch_ub[L23,20]: P[L23,20] <= 4.5
 branch_lb[L23,20]: P[L23,20] >= -4.5
 dc_flow[L34,20]: - 500 theta[3,20] + 500 theta[4,20] + P[L34,20] = 0
 branch_ub[L34,20]: P[L34,20] <= 4
 branch_lb[L34,20]: P[L34,20] >= -4
 dc_flow[L45,20]: - 454.5454545454546 theta[4,20]
   + 454.5454545454546 theta[5,20] + P[L45,20] = 0
 branch_ub[L45,20]: P[L45,20] <= 3.5
 branch_lb[L45,20]: P[L45,20] >= -3.5
 dc_flow[L56,20]: - 555.5555555555555 theta[5,20]
   + 555.5555555555555 theta[6,20] + P[L56,20] = 0
 branch_ub[L56,20]: P[L56,20] <= 3
 branch_lb[L56,20]: P[L56,20] >= -3
 p_balance[1,20]: - P[L12,20] + p_grid[20] = 0
 p_balance[2,20]: - P[L12,20] + P[L23,20] = -0.748
 p_balance[3,20]: - P[L23,20] + P[L34,20] = -0.528
 p_balance[4,20]: - P[L34,20] + P[L45,20] = -0.585
 p_balance[5,20]: - P[L45,20] + P[L56,20] = -0.528
 p_balance[6,20]: P[L56,20] + p_dg[20] = 0.24
 slack_theta[21]: theta[1,21] = 0
 dc_flow[L12,21]: - 333.3333333333334 theta[1,21]
   + 333.3333333333334 theta[2,21] + P[L12,21] = 0
 branch_ub[L12,21]: P[L12,21] <= 6
 branch_lb[L12,21]: P[L12,21] >= -6
 dc_flow[L23,21]: - 400 theta[2,21] + 400 theta[3,21] + P[L23,21] = 0
 branch_ub[L23,21]: P[L23,21] <= 4.5
 branch_lb[L23,21]: P[L23,21] >= -4.5
 dc_flow[L34,21]: - 500 theta[3,21] + 500 theta[4,21] + P[L34,21] = 0
 branch_ub[L34,21]: P[L34,21] <= 4
 branch_lb[L34,21]: P[L34,21] >= -4
 dc_flow[L45,21]: - 454.5454545454546 theta[4,21]
   + 454.5454545454546 theta[5,21] + P[L45,21] = 0
 branch_ub[L45,21]: P[L45,21] <= 3.5
 branch_lb[L45,21]: P[L45,21] >= -3.5
 dc_flow[L56,21]: - 555.5555555555555 theta[5,21]
   + 555.5555555555555 theta[6,21] + P[L56,21] = 0
 branch_ub[L56,21]: P[L56,21] <= 3
 branch_lb[L56,21]: P[L56,21] >= -3
 p_balance[1,21]: - P[L12,21] + p_grid[21] = 0
 p_balance[2,21]: - P[L12,21] + P[L23,21] = -0.6375
 p_balance[3,21]: - P[L23,21] + P[L34,21] = -0.484
 p_balance[4,21]: - P[L34,21] + P[L45,21] = -0.5625
 p_balance[5,21]: - P[L45,21] + P[L56,21] = -0.45
 p_balance[6,21]: P[L56,21] + p_dg[21] = 0.22
 slack_theta[22]: theta[1,22] = 0
 dc_flow[L12,22]: - 333.3333333333334 theta[1,22]
   + 333.3333333333334 theta[2,22] + P[L12,22] = 0
 branch_ub[L12,22]: P[L12,22] <= 6
 branch_lb[L12,22]: P[L12,22] >= -6
 dc_flow[L23,22]: - 400 theta[2,22] + 400 theta[3,22] + P[L23,22] = 0
 branch_ub[L23,22]: P[L23,22] <= 4.5
 branch_lb[L23,22]: P[L23,22] >= -4.5
 dc_flow[L34,22]: - 500 theta[3,22] + 500 theta[4,22] + P[L34,22] = 0
 branch_ub[L34,22]: P[L34,22] <= 4
 branch_lb[L34,22]: P[L34,22] >= -4
 dc_flow[L45,22]: - 454.5454545454546 theta[4,22]
   + 454.5454545454546 theta[5,22] + P[L45,22] = 0
 branch_ub[L45,22]: P[L45,22] <= 3.5
 branch_lb[L45,22]: P[L45,22] >= -3.5
 dc_flow[L56,22]: - 555.5555555555555 theta[5,22]
   + 555.5555555555555 theta[6,22] + P[L56,22] = 0
 branch_ub[L56,22]: P[L56,22] <= 3
 branch_lb[L56,22]: P[L56,22] >= -3
 p_balance[1,22]: - P[L12,22] + p_grid[22] = 0
 p_balance[2,22]: - P[L12,22] + P[L23,22] = -0.51
 p_balance[3,22]: - P[L23,22] + P[L34,22] = -0.44
 p_balance[4,22]: - P[L34,22] + P[L45,22] = -0.5475
 p_balance[5,22]: - P[L45,22] + P[L56,22] = -0.36
 p_balance[6,22]: P[L56,22] + p_dg[22] = 0.2
 slack_theta[23]: theta[1,23] = 0
 dc_flow[L12,23]: - 333.3333333333334 theta[1,23]
   + 333.3333333333334 theta[2,23] + P[L12,23] = 0
 branch_ub[L12,23]: P[L12,23] <= 6
 branch_lb[L12,23]: P[L12,23] >= -6
 dc_flow[L23,23]: - 400 theta[2,23] + 400 theta[3,23] + P[L23,23] = 0
 branch_ub[L23,23]: P[L23,23] <= 4.5
 branch_lb[L23,23]: P[L23,23] >= -4.5
 dc_flow[L34,23]: - 500 theta[3,23] + 500 theta[4,23] + P[L34,23] = 0
 branch_ub[L34,23]: P[L34,23] <= 4
 branch_lb[L34,23]: P[L34,23] >= -4
 dc_flow[L45,23]: - 454.5454545454546 theta[4,23]
   + 454.5454545454546 theta[5,23] + P[L45,23] = 0
 branch_ub[L45,23]: P[L45,23] <= 3.5
 branch_lb[L45,23]: P[L45,23] >= -3.5
 dc_flow[L56,23]: - 555.5555555555555 theta[5,23]
   + 555.5555555555555 theta[6,23] + P[L56,23] = 0
 branch_ub[L56,23]: P[L56,23] <= 3
 branch_lb[L56,23]: P[L56,23] >= -3
 p_balance[1,23]: - P[L12,23] + p_grid[23] = 0
 p_balance[2,23]: - P[L12,23] + P[L23,23] = -0.442
 p_balance[3,23]: - P[L23,23] + P[L34,23] = -0.407
 p_balance[4,23]: - P[L34,23] + P[L45,23] = -0.5325
 p_balance[5,23]: - P[L45,23] + P[L56,23] = -0.312
 p_balance[6,23]: P[L56,23] + p_dg[23] = 0.185
Bounds
 theta[1,0] free
 theta[1,1] free
 theta[1,2] free
 theta[1,3] free
 theta[1,4] free
 theta[1,5] free
 theta[1,6] free
 theta[1,7] free
 theta[1,8] free
 theta[1,9] free
 theta[1,10] free
 theta[1,11] free
 theta[1,12] free
 theta[1,13] free
 theta[1,14] free
 theta[1,15] free
 theta[1,16] free
 theta[1,17] free
 theta[1,18] free
 theta[1,19] free
 theta[1,20] free
 theta[1,21] free
 theta[1,22] free
 theta[1,23] free
 theta[2,0] free
 theta[2,1] free
 theta[2,2] free
 theta[2,3] free
 theta[2,4] free
 theta[2,5] free
 theta[2,6] free
 theta[2,7] free
 theta[2,8] free
 theta[2,9] free
 theta[2,10] free
 theta[2,11] free
 theta[2,12] free
 theta[2,13] free
 theta[2,14] free
 theta[2,15] free
 theta[2,16] free
 theta[2,17] free
 theta[2,18] free
 theta[2,19] free
 theta[2,20] free
 theta[2,21] free
 theta[2,22] free
 theta[2,23] free
 theta[3,0] free
 theta[3,1] free
 theta[3,2] free
 theta[3,3] free
 theta[3,4] free
 theta[3,5] free
 theta[3,6] free
 theta[3,7] free
 theta[3,8] free
 theta[3,9] free
 theta[3,10] free
 theta[3,11] free
 theta[3,12] free
 theta[3,13] free
 theta[3,14] free
 theta[3,15] free
 theta[3,16] free
 theta[3,17] free
 theta[3,18] free
 theta[3,19] free
 theta[3,20] free
 theta[3,21] free
 theta[3,22] free
 theta[3,23] free
 theta[4,0] free
 theta[4,1] free
 theta[4,2] free
 theta[4,3] free
 theta[4,4] free
 theta[4,5] free
 theta[4,6] free
 theta[4,7] free
 theta[4,8] free
 theta[4,9] free
 theta[4,10] free
 theta[4,11] free
 theta[4,12] free
 theta[4,13] free
 theta[4,14] free
 theta[4,15] free
 theta[4,16] free
 theta[4,17] free
 theta[4,18] free
 theta[4,19] free
 theta[4,20] free
 theta[4,21] free
 theta[4,22] free
 theta[4,23] free
 theta[5,0] free
 theta[5,1] free
 theta[5,2] free
 theta[5,3] free
 theta[5,4] free
 theta[5,5] free
 theta[5,6] free
 theta[5,7] free
 theta[5,8] free
 theta[5,9] free
 theta[5,10] free
 theta[5,11] free
 theta[5,12] free
 theta[5,13] free
 theta[5,14] free
 theta[5,15] free
 theta[5,16] free
 theta[5,17] free
 theta[5,18] free
 theta[5,19] free
 theta[5,20] free
 theta[5,21] free
 theta[5,22] free
 theta[5,23] free
 theta[6,0] free
 theta[6,1] free
 theta[6,2] free
 theta[6,3] free
 theta[6,4] free
 theta[6,5] free
 theta[6,6] free
 theta[6,7] free
 theta[6,8] free
 theta[6,9] free
 theta[6,10] free
 theta[6,11] free
 theta[6,12] free
 theta[6,13] free
 theta[6,14] free
 theta[6,15] free
 theta[6,16] free
 theta[6,17] free
 theta[6,18] free
 theta[6,19] free
 theta[6,20] free
 theta[6,21] free
 theta[6,22] free
 theta[6,23] free
 P[L12,0] free
 P[L12,1] free
 P[L12,2] free
 P[L12,3] free
 P[L12,4] free
 P[L12,5] free
 P[L12,6] free
 P[L12,7] free
 P[L12,8] free
 P[L12,9] free
 P[L12,10] free
 P[L12,11] free
 P[L12,12] free
 P[L12,13] free
 P[L12,14] free
 P[L12,15] free
 P[L12,16] free
 P[L12,17] free
 P[L12,18] free
 P[L12,19] free
 P[L12,20] free
 P[L12,21] free
 P[L12,22] free
 P[L12,23] free
 P[L23,0] free
 P[L23,1] free
 P[L23,2] free
 P[L23,3] free
 P[L23,4] free
 P[L23,5] free
 P[L23,6] free
 P[L23,7] free
 P[L23,8] free
 P[L23,9] free
 P[L23,10] free
 P[L23,11] free
 P[L23,12] free
 P[L23,13] free
 P[L23,14] free
 P[L23,15] free
 P[L23,16] free
 P[L23,17] free
 P[L23,18] free
 P[L23,19] free
 P[L23,20] free
 P[L23,21] free
 P[L23,22] free
 P[L23,23] free
 P[L34,0] free
 P[L34,1] free
 P[L34,2] free
 P[L34,3] free
 P[L34,4] free
 P[L34,5] free
 P[L34,6] free
 P[L34,7] free
 P[L34,8] free
 P[L34,9] free
 P[L34,10] free
 P[L34,11] free
 P[L34,12] free
 P[L34,13] free
 P[L34,14] free
 P[L34,15] free
 P[L34,16] free
 P[L34,17] free
 P[L34,18] free
 P[L34,19] free
 P[L34,20] free
 P[L34,21] free
 P[L34,22] free
 P[L34,23] free
 P[L45,0] free
 P[L45,1] free
 P[L45,2] free
 P[L45,3] free
 P[L45,4] free
 P[L45,5] free
 P[L45,6] free
 P[L45,7] free
 P[L45,8] free
 P[L45,9] free
 P[L45,10] free
 P[L45,11] free
 P[L45,12] free
 P[L45,13] free
 P[L45,14] free
 P[L45,15] free
 P[L45,16] free
 P[L45,17] free
 P[L45,18] free
 P[L45,19] free
 P[L45,20] free
 P[L45,21] free
 P[L45,22] free
 P[L45,23] free
 P[L56,0] free
 P[L56,1] free
 P[L56,2] free
 P[L56,3] free
 P[L56,4] free
 P[L56,5] free
 P[L56,6] free
 P[L56,7] free
 P[L56,8] free
 P[L56,9] free
 P[L56,10] free
 P[L56,11] free
 P[L56,12] free
 P[L56,13] free
 P[L56,14] free
 P[L56,15] free
 P[L56,16] free
 P[L56,17] free
 P[L56,18] free
 P[L56,19] free
 P[L56,20] free
 P[L56,21] free
 P[L56,22] free
 P[L56,23] free
 p_grid[0] <= 6
 p_grid[1] <= 6
 p_grid[2] <= 6
 p_grid[3] <= 6
 p_grid[4] <= 6
 p_grid[5] <= 6
 p_grid[6] <= 6
 p_grid[7] <= 6
 p_grid[8] <= 6
 p_grid[9] <= 6
 p_grid[10] <= 6
 p_grid[11] <= 6
 p_grid[12] <= 6
 p_grid[13] <= 6
 p_grid[14] <= 6
 p_grid[15] <= 6
 p_grid[16] <= 6
 p_grid[17] <= 6
 p_grid[18] <= 6
 p_grid[19] <= 6
 p_grid[20] <= 6
 p_grid[21] <= 6
 p_grid[22] <= 6
 p_grid[23] <= 6
 p_dg[0] <= 0.8
 p_dg[1] <= 0.8
 p_dg[2] <= 0.8
 p_dg[3] <= 0.8
 p_dg[4] <= 0.8
 p_dg[5] <= 0.8
 p_dg[6] <= 0.8
 p_dg[7] <= 0.8
 p_dg[8] <= 0.8
 p_dg[9] <= 0.8
 p_dg[10] <= 0.8
 p_dg[11] <= 0.8
 p_dg[12] <= 0.8
 p_dg[13] <= 0.8
 p_dg[14] <= 0.8
 p_dg[15] <= 0.8
 p_dg[16] <= 0.8
 p_dg[17] <= 0.8
 p_dg[18] <= 0.8
 p_dg[19] <= 0.8
 p_dg[20] <= 0.8
 p_dg[21] <= 0.8
 p_dg[22] <= 0.8
 p_dg[23] <= 0.8
End
