// Host-side unit tests for the LoadCellController class.
//
// Only the SPIFFS-independent methods are exercised : add_loadcell,
// per-cell get/set offset and scale, delegation of read/weight, the
// per-cell tare(), n_readings setters, range checks, mass_from_raw
// math. The persistence / calibration interactive paths
// (save_*_to_persistent_memory, read_*_from_persistent_memory,
// tare_all_loadcells, calibrate_all_loadcells, easy_start_with_params)
// touch SPIFFS or EEPROM, neither of which are stubbed here ; testing
// them requires AUnit on a real Firebeetle.

#include "LoadCellController.h"
#include "LoadCell.h"
#include <cstdio>

static int passes = 0, failures = 0;
static const char* current_test = "(none)";

#define TEST(name)                                                 \
    static void name();                                            \
    static void run_##name() { current_test = #name; name(); }     \
    static void name()

#define ASSERT_EQ(a, b) do {                                       \
    long long _a = (long long)(a), _b = (long long)(b);            \
    if (_a != _b) {                                                \
        printf("  FAIL %s:%d in %s : got %lld, expected %lld\n",   \
               __FILE__, __LINE__, current_test, _a, _b);          \
        failures++;                                                \
    } else passes++;                                               \
} while(0)

#define ASSERT_TRUE(x) do {                                        \
    if (!(x)) {                                                    \
        printf("  FAIL %s:%d in %s : expected (%s) to be true\n",  \
               __FILE__, __LINE__, current_test, #x);              \
        failures++;                                                \
    } else passes++;                                               \
} while(0)

#define ASSERT_NEAR(a, b, tol) do {                                \
    double _a = (double)(a), _b = (double)(b), _t = (double)(tol); \
    if ((_a - _b) > _t || (_b - _a) > _t) {                        \
        printf("  FAIL %s:%d in %s : %.4f not within %.4f of %.4f\n",     \
               __FILE__, __LINE__, current_test, _a, _t, _b);      \
        failures++;                                                \
    } else passes++;                                               \
} while(0)

// ----------------------------------------------------------------------------
// Tests
// ----------------------------------------------------------------------------

TEST(add_loadcell_increments_count) {
    LoadCellController ctrl;
    LoadCell a, b, c;
    ASSERT_EQ(ctrl.number_of_loadcells(), 0);
    ctrl.add_loadcell(a);
    ASSERT_EQ(ctrl.number_of_loadcells(), 1);
    ctrl.add_loadcell(b);
    ctrl.add_loadcell(c);
    ASSERT_EQ(ctrl.number_of_loadcells(), 3);
}

TEST(is_loadcell_num_in_range) {
    LoadCellController ctrl;
    LoadCell a, b;
    ctrl.add_loadcell(a);
    ctrl.add_loadcell(b);
    ASSERT_TRUE(ctrl.is_loadcell_num_in_range(1));
    ASSERT_TRUE(ctrl.is_loadcell_num_in_range(2));
    ASSERT_TRUE(!ctrl.is_loadcell_num_in_range(0));
    ASSERT_TRUE(!ctrl.is_loadcell_num_in_range(3));
}

TEST(get_set_offset_delegates_per_cell) {
    LoadCellController ctrl;
    LoadCell a, b;
    ctrl.add_loadcell(a);
    ctrl.add_loadcell(b);
    ctrl.set_offset(1, -1212208.0f);
    ctrl.set_offset(2, -1213500.0f);
    // Check via the controller getter
    ASSERT_NEAR(ctrl.get_offset(1), -1212208.0, 0.5);
    ASSERT_NEAR(ctrl.get_offset(2), -1213500.0, 0.5);
    // Check that cells are independent
    ASSERT_TRUE(ctrl.get_offset(1) != ctrl.get_offset(2));
}

TEST(get_set_scale_delegates_per_cell) {
    LoadCellController ctrl;
    LoadCell a, b, c;
    ctrl.add_loadcell(a);
    ctrl.add_loadcell(b);
    ctrl.add_loadcell(c);
    ctrl.set_scale(1, -15701.53f);
    ctrl.set_scale(2, -14743.76f);
    ctrl.set_scale(3, +12345.67f);
    ASSERT_NEAR(ctrl.get_scale(1), -15701.53, 0.01);
    ASSERT_NEAR(ctrl.get_scale(2), -14743.76, 0.01);
    ASSERT_NEAR(ctrl.get_scale(3), +12345.67, 0.01);
}

TEST(read_raw_average_via_controller_uses_correct_cell) {
    LoadCellController ctrl;
    LoadCell a, b;
    a.mock_reset(); b.mock_reset();
    ctrl.add_loadcell(a);
    ctrl.add_loadcell(b);
    a.set_weight_n_readings(1); b.set_weight_n_readings(1);
    a.mock_push(1000L);
    b.mock_push(2000L);
    ASSERT_EQ(ctrl.read_raw_average(1), 1000L);
    ASSERT_EQ(ctrl.read_raw_average(2), 2000L);
}

TEST(mass_from_raw_per_cell) {
    LoadCellController ctrl;
    LoadCell a, b;
    ctrl.add_loadcell(a);
    ctrl.add_loadcell(b);
    ctrl.set_offset(1, 0.0f);
    ctrl.set_scale(1, 1000.0f);
    ctrl.set_offset(2, -1000000.0f);
    ctrl.set_scale(2, -10000.0f);

    // cell 1 : (50000 - 0) / 1000 = 50 g
    ASSERT_NEAR(ctrl.mass_from_raw(1, 50000L), 50.0, 0.01);
    // cell 2 : (-1500000 - (-1000000)) / -10000 = -500000 / -10000 = 50 g
    ASSERT_NEAR(ctrl.mass_from_raw(2, -1500000L), 50.0, 0.01);
}

TEST(get_weight_via_controller_uses_correct_cell_calibration) {
    LoadCellController ctrl;
    LoadCell a, b;
    a.mock_reset(); b.mock_reset();
    ctrl.add_loadcell(a);
    ctrl.add_loadcell(b);
    ctrl.set_offset(1, -1212208.0f);
    ctrl.set_scale(1, -15701.53f);
    ctrl.set_offset(2, -500000.0f);
    ctrl.set_scale(2, -10000.0f);
    a.set_weight_n_readings(1); b.set_weight_n_readings(1);
    // raw such that mass = 100 g on cell 1 :
    //   raw = offset + 100*scale = -1212208 + 100*-15701.53 = -2782361
    a.mock_push(-2782361L);
    // raw such that mass = 50 g on cell 2 :
    //   raw = -500000 + 50*-10000 = -1000000
    b.mock_push(-1000000L);
    ASSERT_NEAR(ctrl.get_weight(1), 100.0, 0.5);
    ASSERT_NEAR(ctrl.get_weight(2), 50.0,  0.5);
}

TEST(set_all_loadcells_n_readings_updates_each_cell) {
    LoadCellController ctrl;
    LoadCell a, b, c;
    ctrl.add_loadcell(a);
    ctrl.add_loadcell(b);
    ctrl.add_loadcell(c);
    ctrl.set_all_loadcells_weight_n_readings(7);
    ASSERT_EQ(a.get_weight_n_readings(), 7);
    ASSERT_EQ(b.get_weight_n_readings(), 7);
    ASSERT_EQ(c.get_weight_n_readings(), 7);

    ctrl.set_all_loadcells_tare_n_readings(11);
    ASSERT_EQ(a.get_tare_n_readings(), 11);
    ASSERT_EQ(b.get_tare_n_readings(), 11);
    ASSERT_EQ(c.get_tare_n_readings(), 11);

    ctrl.set_all_loadcells_scale_coeff_n_readings(13);
    ASSERT_EQ(a.get_scale_coeff_n_readings(), 13);
    ASSERT_EQ(b.get_scale_coeff_n_readings(), 13);
    ASSERT_EQ(c.get_scale_coeff_n_readings(), 13);
}

TEST(tare_per_cell_does_not_affect_other_cells) {
    LoadCellController ctrl;
    LoadCell a, b;
    a.mock_reset(); b.mock_reset();
    ctrl.add_loadcell(a);
    ctrl.add_loadcell(b);
    ctrl.set_offset(1, -100.0f);
    ctrl.set_offset(2, -200.0f);
    a.set_tare_n_readings(1);
    a.mock_push(99999L);
    ctrl.tare(1);
    ASSERT_EQ(a.get_offset(), 99999L);          // cell 1 retared
    ASSERT_NEAR(b.get_offset(), -200.0, 0.5);   // cell 2 untouched
}

TEST(set_get_mouse_weight) {
    LoadCellController ctrl;
    ASSERT_NEAR(ctrl.get_mouse_weight(), 20.0, 0.01);   // default
    ctrl.set_mouse_weight(25.5f);
    ASSERT_NEAR(ctrl.get_mouse_weight(), 25.5, 0.01);
    ctrl.set_mouse_weight(-1.0f);                       // negative ignored
    ASSERT_NEAR(ctrl.get_mouse_weight(), 25.5, 0.01);
}

TEST(get_n_readings_per_cell) {
    LoadCellController ctrl;
    LoadCell a, b;
    ctrl.add_loadcell(a);
    ctrl.add_loadcell(b);
    ctrl.set_tare_n_readings(1, 33);
    ctrl.set_tare_n_readings(2, 44);
    ASSERT_EQ(ctrl.get_tare_n_readings(1), 33);
    ASSERT_EQ(ctrl.get_tare_n_readings(2), 44);
}

TEST(read_raw_average_propagates_corruption_handling) {
    LoadCellController ctrl;
    LoadCell a;
    a.mock_reset();
    ctrl.add_loadcell(a);
    a.set_weight_n_readings(3);
    // Three reads, each with one corrupt then one good.
    a.mock_push(-1L); a.mock_push(100L);
    a.mock_push(-1L); a.mock_push(200L);
    a.mock_push(-1L); a.mock_push(300L);
    long avg = ctrl.read_raw_average(1);
    // safe_read returns 100, 200, 300 → avg = 200
    ASSERT_EQ(avg, 200L);
    ASSERT_EQ(a.corrupted_neg1, 3);
    ASSERT_EQ(a.total_reads, 6);
}

// ----------------------------------------------------------------------------
// main
// ----------------------------------------------------------------------------
int main() {
    printf("LoadCellController host-side unit tests\n");
    printf("=======================================\n");

    run_add_loadcell_increments_count();
    run_is_loadcell_num_in_range();
    run_get_set_offset_delegates_per_cell();
    run_get_set_scale_delegates_per_cell();
    run_read_raw_average_via_controller_uses_correct_cell();
    run_mass_from_raw_per_cell();
    run_get_weight_via_controller_uses_correct_cell_calibration();
    run_set_all_loadcells_n_readings_updates_each_cell();
    run_tare_per_cell_does_not_affect_other_cells();
    run_set_get_mouse_weight();
    run_get_n_readings_per_cell();
    run_read_raw_average_propagates_corruption_handling();

    printf("\n%d passed, %d failed\n", passes, failures);
    return failures == 0 ? 0 : 1;
}
