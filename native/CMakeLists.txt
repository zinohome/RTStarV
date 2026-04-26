cmake_minimum_required(VERSION 3.16)
project(rtstarv_imu LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

include_directories(include)

# Parser library (pure functions, no USB dependency)
add_library(rtstarv_parser STATIC
    src/imu_parser.cpp
    src/attitude_solver.cpp
)
target_include_directories(rtstarv_parser PUBLIC include src)

# Parser tests (always buildable, no hidapi needed)
add_executable(test_parser tests/test_parser.cpp)
target_link_libraries(test_parser rtstarv_parser)

enable_testing()
add_test(NAME parser_tests COMMAND test_parser)

# Full driver shared library (requires hidapi)
find_package(PkgConfig QUIET)
if(PkgConfig_FOUND)
    pkg_check_modules(HIDAPI hidapi-libusb)
endif()

if(HIDAPI_FOUND OR WIN32)
    add_library(rtstarv_imu SHARED
        src/imu_parser.cpp
        src/attitude_solver.cpp
        src/usb_device.cpp
        src/imu_reader.cpp
        src/rtstarv_imu.cpp
    )
    target_include_directories(rtstarv_imu PUBLIC include PRIVATE src)

    if(HIDAPI_FOUND)
        target_include_directories(rtstarv_imu PRIVATE ${HIDAPI_INCLUDE_DIRS})
        target_link_libraries(rtstarv_imu ${HIDAPI_LIBRARIES} pthread)
    elseif(WIN32)
        target_link_libraries(rtstarv_imu hidapi)
    endif()

    set_target_properties(rtstarv_imu PROPERTIES
        OUTPUT_NAME "rtstarv_imu"
        VERSION 0.1.0
    )

    if(NOT WIN32)
        set_target_properties(rtstarv_imu PROPERTIES
            CXX_VISIBILITY_PRESET hidden
        )
    endif()

    message(STATUS "Building full rtstarv_imu shared library")
else()
    message(STATUS "hidapi not found — building parser/tests only (full driver skipped)")
endif()
