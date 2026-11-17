<?php
/**
 * Stand-ins for the WordPress functions the ticket login plugin calls, so its behaviour runs under the PHP CLI with
 * no WordPress (D07 T02 section 1). `test_ticket_login.py` drives it: one JSON case on stdin, one JSON report on
 * stdout when the script ends, however it ends (the plugin's `exit` after the redirect, `wp_die`, or the end).
 *
 * The case: `plugins` (the plugin files to load, in order), `query` (absent, or the value of `conclave_ticket`,
 * which may be an array), `option` (absent, or the stored ticket), `gone_before_delete` (another request removed
 * the ticket between this one's read and its delete), `replace_before_delete` (another request used the ticket and
 * the opener stored this newer one in that gap), `users` (by ID: `login` and `caps`), `run_init` (whether to run the
 * `init` callbacks). The options table holds each value serialized, as WordPress's does, and `$wpdb` reads and deletes
 * against it. The report: every call in order, the options left and
 * the `init` callbacks registered.
 *
 * @package Conclave
 */

define( 'ABSPATH', __DIR__ . '/' );

$GLOBALS['harness_case']    = json_decode( stream_get_contents( STDIN ), true );
$GLOBALS['harness_calls']   = array();
$GLOBALS['harness_actions'] = array();
$GLOBALS['harness_options'] = array();
if ( array_key_exists( 'option', $GLOBALS['harness_case'] ) ) {
	$GLOBALS['harness_options']['conclave_login_ticket'] = $GLOBALS['harness_case']['option'];
}
if ( array_key_exists( 'query', $GLOBALS['harness_case'] ) ) {
	$_GET['conclave_ticket'] = $GLOBALS['harness_case']['query'];
}

function harness_record( $name, $args ) {
	$GLOBALS['harness_calls'][] = array( $name, $args );
}

register_shutdown_function(
	function () {
		$init = array();
		foreach ( $GLOBALS['harness_actions'] as $action ) {
			if ( 'init' === $action[0] ) {
				$init[] = array( $action[1], $action[2] );
			}
		}
		echo json_encode(
			array(
				'calls'   => $GLOBALS['harness_calls'],
				'options' => (object) $GLOBALS['harness_options'],
				'init'    => $init,
			)
		);
	}
);

function add_action( $hook, $callback, $priority = 10, $accepted_args = 1 ) {
	harness_record( 'add_action', array( $hook, $callback, $priority ) );
	$GLOBALS['harness_actions'][] = array( $hook, $callback, $priority );
}

function do_action( $hook, ...$args ) {
	$described = array_map(
		function ( $arg ) {
			return is_object( $arg ) ? array( 'object' => $arg->ID ) : $arg;
		},
		$args
	);
	harness_record( 'do_action', array_merge( array( $hook ), $described ) );
}

/**
 * The two `$wpdb` calls the plugin makes, against the options table above.
 */
class Harness_Wpdb {
	public $options = 'wp_options';

	public function prepare( $sql, ...$args ) {
		return array( $sql, $args );
	}

	public function get_var( $query ) {
		$name = $query[1][0];
		harness_record( 'wpdb_get_var', array( $name ) );
		return array_key_exists( $name, $GLOBALS['harness_options'] ) ? serialize( $GLOBALS['harness_options'][ $name ] ) : null;
	}

	public function query( $query ) {
		$name  = $query[1][0];
		$value = isset( $query[1][1] ) ? $query[1][1] : null;
		$case                 = $GLOBALS['harness_case'];
		if ( ! empty( $case['gone_before_delete'] ) ) {
			unset( $GLOBALS['harness_options'][ $name ] );
		}
		if ( array_key_exists( 'replace_before_delete', $case ) ) {
			$GLOBALS['harness_options'][ $name ] = $case['replace_before_delete'];
		}
		harness_record( 'wpdb_delete', array( $name ) );
		if ( 'DELETE FROM wp_options WHERE option_name = %s' === $query[0] ) {
			// By name only, as delete_option does: whatever ticket is there now goes.
			$had = array_key_exists( $name, $GLOBALS['harness_options'] );
			unset( $GLOBALS['harness_options'][ $name ] );
			return $had ? 1 : 0;
		}
		if ( 'DELETE FROM wp_options WHERE option_name = %s AND option_value = %s' !== $query[0] ) {
			return false;
		}
		if ( array_key_exists( $name, $GLOBALS['harness_options'] ) && serialize( $GLOBALS['harness_options'][ $name ] ) === $value ) {
			unset( $GLOBALS['harness_options'][ $name ] );
			return 1;
		}
		return 0;
	}
}
$GLOBALS['wpdb'] = new Harness_Wpdb();

function maybe_unserialize( $value ) {
	if ( ! is_string( $value ) ) {
		return $value;
	}
	$out = @unserialize( $value );
	return ( false === $out && 'b:0;' !== $value ) ? $value : $out;
}

function wp_cache_delete( $key, $group = '' ) {
	harness_record( 'wp_cache_delete', array( $key, $group ) );
	return true;
}

function get_option( $name, $default = false ) {
	harness_record( 'get_option', array( $name ) );
	return array_key_exists( $name, $GLOBALS['harness_options'] ) ? $GLOBALS['harness_options'][ $name ] : $default;
}

function delete_option( $name ) {
	harness_record( 'delete_option', array( $name ) );
	$had = array_key_exists( $name, $GLOBALS['harness_options'] );
	unset( $GLOBALS['harness_options'][ $name ] );
	return $had;
}

function get_userdata( $id ) {
	harness_record( 'get_userdata', array( $id ) );
	$users = isset( $GLOBALS['harness_case']['users'] ) ? $GLOBALS['harness_case']['users'] : array();
	if ( ! isset( $users[ (string) $id ] ) ) {
		return false;
	}
	$user             = new stdClass();
	$user->ID         = $id;
	$user->user_login = $users[ (string) $id ]['login'];
	$user->caps       = $users[ (string) $id ]['caps'];
	return $user;
}

function user_can( $user, $capability ) {
	harness_record( 'user_can', array( $user->ID, $capability ) );
	return in_array( $capability, $user->caps, true );
}

function wp_unslash( $value ) {
	return $value;
}

function esc_html__( $text, $domain = 'default' ) {
	return $text;
}

function nocache_headers() {
	harness_record( 'nocache_headers', array() );
}

function wp_set_current_user( $id ) {
	harness_record( 'wp_set_current_user', array( $id ) );
}

function wp_set_auth_cookie( $id, $remember = false ) {
	harness_record( 'wp_set_auth_cookie', array( $id, $remember ) );
}

function admin_url() {
	return 'https://example.com/wp-admin/';
}

function wp_safe_redirect( $location ) {
	harness_record( 'wp_safe_redirect', array( $location ) );
	return true;
}

function wp_die( $message = '', $title = '', $args = array() ) {
	harness_record( 'wp_die', array( $message, isset( $args['response'] ) ? $args['response'] : null ) );
	exit;
}

foreach ( $GLOBALS['harness_case']['plugins'] as $plugin ) {
	require $plugin;
}
if ( ! empty( $GLOBALS['harness_case']['run_init'] ) ) {
	foreach ( $GLOBALS['harness_actions'] as $action ) {
		if ( 'init' === $action[0] ) {
			call_user_func( $action[1] );
		}
	}
}
